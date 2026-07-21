import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
import pandas as pd
import yaml
from urllib.parse import urlparse

# Add current directory and src directory to sys.path to ensure correct imports
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent))

from db import get_db_connection

def setup_database(conn):
    schema_file = Path("sql/create_tables.sql")
    if not schema_file.exists():
        schema_file = Path(__file__).parent.parent / "sql" / "create_tables.sql"
        
    print(f"Executing database schema from {schema_file.resolve()}...")
    with open(schema_file, 'r') as f:
        schema_sql = f.read()
        
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()
    print("Database setup complete.")

def get_source_base_urls():
    # Load configuration
    config_path = Path("config/sources.yaml")
    if not config_path.exists():
        config_path = Path(__file__).parent.parent / "config" / "sources.yaml"
        
    base_urls = {}
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            for src in config.get('sources', []):
                base_urls[src['name']] = src['url']
        except Exception as e:
            print(f"Warning: Could not parse config for base URLs: {e}")
    return base_urls

def prune_old_scraps(conn, keep_last_n=3):
    """
    Keep only articles from the last N distinct scrap runs per source in fact_article.
    Delete older articles and orphaned keywords from dim_keyword.
    """
    print(f"Pruning database records: Keeping only the last {keep_last_n} scheduled scraps per source...")
    with conn.cursor() as cur:
        # Delete articles older than the last N distinct scraped_at batches per source_id
        cur.execute("""
            DELETE FROM fact_article
            WHERE article_id IN (
                SELECT article_id FROM (
                    SELECT article_id,
                           DENSE_RANK() OVER (PARTITION BY source_id ORDER BY scraped_at DESC) as rank
                    FROM fact_article
                ) ranked
                WHERE rank > %s
            );
        """, (keep_last_n,))
        deleted_articles = cur.rowcount
        
        # Clean up orphaned keywords in dim_keyword
        cur.execute("""
            DELETE FROM dim_keyword
            WHERE keyword_id NOT IN (SELECT DISTINCT keyword_id FROM bridge_article_keyword);
        """)
        deleted_keywords = cur.rowcount
        
    conn.commit()
    print(f"Storage maintenance complete: Deleted {deleted_articles} older articles and {deleted_keywords} orphaned keywords.")

def prune_old_local_data(keep_last_n=3):
    """
    Clean up older date directories in data/raw and data/staging to keep local storage efficient.
    """
    for base_dir_name in ["data/raw", "data/staging"]:
        base_path = Path(base_dir_name)
        if not base_path.exists():
            continue
        dirs = [d for d in base_path.iterdir() if d.is_dir()]
        dirs.sort(key=lambda d: d.name, reverse=True)
        if len(dirs) > keep_last_n:
            for old_dir in dirs[keep_last_n:]:
                print(f"Cleaning up old local data directory: {old_dir}")
                import shutil
                shutil.rmtree(old_dir, ignore_errors=True)

def main():
    parser = argparse.ArgumentParser(description="Load transformed data into PostgreSQL.")
    parser.add_argument('--date', type=str, help="Date folder to process (YYYY-MM-DD). Defaults to today.")
    args = parser.parse_args()
    
    date_str = args.date if args.date else datetime.utcnow().strftime('%Y-%m-%d')
    staging_file = Path("data/staging") / date_str / "articles_clean.parquet"
    
    if not staging_file.exists():
        print(f"Staging file not found: {staging_file}")
        sys.exit(1)
        
    # Read Parquet staging file
    try:
        df = pd.read_parquet(staging_file)
    except Exception as e:
        print(f"Failed to read Parquet staging data: {e}")
        sys.exit(1)
        
    # Connect to DB
    try:
        conn = get_db_connection()
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)
        
    # Ensure tables are created
    try:
        setup_database(conn)
    except Exception as e:
        print(f"Database setup failed: {e}")
        conn.close()
        sys.exit(1)
        
    base_urls = get_source_base_urls()
    total_scraped = len(df)
    inserted_count = 0
    
    try:
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                source_name = row['source_name']
                # Determine base url
                base_url = base_urls.get(source_name)
                if not base_url:
                    parsed_url = urlparse(row['url'])
                    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                
                # 1. Upsert dim_source
                cur.execute("""
                    INSERT INTO dim_source (source_name, base_url)
                    VALUES (%s, %s)
                    ON CONFLICT (source_name) DO UPDATE SET base_url = EXCLUDED.base_url
                    RETURNING source_id;
                """, (source_name, base_url))
                source_id = cur.fetchone()[0]
                
                # 2. Insert fact_article
                summary = row['summary'] if pd.notna(row['summary']) else None
                cur.execute("""
                    INSERT INTO fact_article (
                        article_id, source_id, headline, summary, url, 
                        sentiment_score, sentiment_label, published_at, scraped_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (article_id) DO NOTHING;
                """, (
                    row['article_id'],
                    source_id,
                    row['headline'],
                    summary,
                    row['url'],
                    row['sentiment_score'],
                    row['sentiment_label'],
                    row['published_at'],
                    row['scraped_at']
                ))
                
                # If row was inserted (not skipped due to conflict)
                if cur.rowcount > 0:
                    inserted_count += 1
                    
                    # 3. Handle keywords and bridge table
                    keywords = row.get('keywords', [])
                    # In some setups pandas lists might be read as numpy arrays
                    if hasattr(keywords, 'tolist'):
                        keywords = keywords.tolist()
                    
                    for kw in keywords:
                        if not kw:
                            continue
                        # Upsert keyword
                        cur.execute("""
                            INSERT INTO dim_keyword (keyword)
                            VALUES (%s)
                            ON CONFLICT (keyword) DO UPDATE SET keyword = EXCLUDED.keyword
                            RETURNING keyword_id;
                        """, (kw,))
                        keyword_id = cur.fetchone()[0]
                        
                        # Insert bridge relation
                        cur.execute("""
                            INSERT INTO bridge_article_keyword (article_id, keyword_id)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING;
                        """, (row['article_id'], keyword_id))
                        
        # Commit transaction
        conn.commit()
        print(f"Data loading complete. Loaded {inserted_count} new articles (total batch: {total_scraped}).")
        
        # Prune older scraps to maintain 3 scheduled scraps per source
        prune_old_scraps(conn, keep_last_n=3)
        prune_old_local_data(keep_last_n=3)

        # Log success
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pipeline_logs (source, status, rows_scraped, rows_loaded)
                VALUES (%s, %s, %s, %s);
            """, ('pipeline_all', 'success', total_scraped, inserted_count))
        conn.commit()
        
    except Exception as e:
        print(f"Error during loading database transaction: {e}")
        try:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pipeline_logs (source, status, rows_scraped, rows_loaded, error_message)
                    VALUES (%s, %s, %s, %s, %s);
                """, ('pipeline_all', 'fail', total_scraped, 0, str(e)))
            conn.commit()
        except Exception as log_ex:
            print(f"Critical error: Failed to log failure to database: {log_ex}")
        finally:
            conn.close()
        sys.exit(1)
        
    conn.close()
    sys.exit(0)

if __name__ == '__main__':
    main()
