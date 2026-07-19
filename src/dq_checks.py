import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
import pandas as pd

# Add current directory and src directory to sys.path to ensure correct imports
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent))

def run_dq_checks(df: pd.DataFrame) -> list:
    errors = []
    
    # Check 1: Empty batch
    if len(df) == 0:
        errors.append("Empty dataset: No rows found in this batch.")
        return errors # Return early if empty since other checks will fail or be irrelevant
        
    # Check 2: Null headlines
    if df['headline'].isnull().any():
        null_count = df['headline'].isnull().sum()
        errors.append(f"Null headlines check failed: {null_count} null headlines found.")
        
    # Check 3: Empty headline strings
    if (df['headline'].str.strip() == '').any():
        empty_count = (df['headline'].str.strip() == '').sum()
        errors.append(f"Empty headlines check failed: {empty_count} blank headlines found.")
        
    # Check 4: Sentiment score range [-1, 1]
    out_of_range = ~df['sentiment_score'].between(-1.0, 1.0)
    if out_of_range.any():
        bad_scores_count = out_of_range.sum()
        errors.append(f"Sentiment score range check failed: {bad_scores_count} scores out of [-1, 1] range.")
        
    # Check 5: Duplicate article_id
    if df['article_id'].duplicated().any():
        dup_count = df['article_id'].duplicated().sum()
        errors.append(f"Duplicate article ID check failed: {dup_count} duplicate article_id values found.")
        
    return errors

def main():
    parser = argparse.ArgumentParser(description="Run data quality checks on staging Parquet files.")
    parser.add_argument('--date', type=str, help="Date folder to process (YYYY-MM-DD). Defaults to today.")
    args = parser.parse_args()
    
    date_str = args.date if args.date else datetime.utcnow().strftime('%Y-%m-%d')
    staging_file = Path("data/staging") / date_str / "articles_clean.parquet"
    
    if not staging_file.exists():
        print(f"Staging Parquet file does not exist: {staging_file}")
        sys.exit(1)
        
    try:
        df = pd.read_parquet(staging_file)
    except Exception as e:
        print(f"Failed to read Parquet file {staging_file}: {e}")
        sys.exit(1)
        
    print(f"Running Data Quality checks on staging data: {staging_file}")
    errors = run_dq_checks(df)
    
    if errors:
        print("\n=== DATA QUALITY GATE FAILED ===")
        for err in errors:
            print(f"- ERROR: {err}")
        print("================================")
        sys.exit(1)
    else:
        print(f"=== DATA QUALITY PASSED ===\nValidated {len(df)} rows successfully with zero errors.")
        sys.exit(0)

if __name__ == '__main__':
    main()
