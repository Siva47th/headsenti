from datetime import timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
from pathlib import Path

# Add project root and src to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent))

from db import get_db_connection

app = FastAPI(title="News Sentiment API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper to run database queries and return dicts
def run_db_query(query: str, params=None, fetch_all=True):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query, params)
            if not cur.description:
                conn.commit()
                conn.close()
                return []
            columns = [desc[0] for desc in cur.description]
            if fetch_all:
                rows = cur.fetchall()
                res = [dict(zip(columns, row)) for row in rows]
            else:
                row = cur.fetchone()
                res = dict(zip(columns, row)) if row else None
        conn.close()
        return res
    except Exception as e:
        print(f"Database query error: {e}")
        return None

# Serve index.html at root url
@app.get("/")
def read_root():
    index_path = Path("frontend/index.html")
    if not index_path.exists():
        index_path = Path(__file__).parent.parent / "frontend" / "index.html"
    return FileResponse(index_path)

@app.get("/api/metrics")
def get_metrics(source: str = None):
    query = """
        SELECT 
            COUNT(*) as total_articles,
            AVG(sentiment_score) as avg_sentiment,
            SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) as pos_count,
            SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) as neg_count,
            SUM(CASE WHEN sentiment_label = 'neutral' THEN 1 ELSE 0 END) as neu_count,
            MAX(scraped_at) as last_scraped_at
        FROM fact_article
    """
    
    params = []
    if source and source != "All Sources":
        query += " WHERE source_id = (SELECT source_id FROM dim_source WHERE source_name = %s)"
        params.append(source)
        
    res = run_db_query(query, tuple(params) if params else None, fetch_all=False)
    
    if not res or res['total_articles'] == 0 or res['total_articles'] is None:
        return {
            "total_articles": 0,
            "avg_sentiment": 0.0,
            "pos_pct": 0.0,
            "neg_pct": 0.0,
            "neu_pct": 0.0,
            "last_scraped_at": "N/A"
        }
        
    total = int(res['total_articles'])
    avg_s = float(res['avg_sentiment']) if res['avg_sentiment'] is not None else 0.0
    pos = int(res['pos_count']) if res['pos_count'] is not None else 0
    neg = int(res['neg_count']) if res['neg_count'] is not None else 0
    
    last_scraped = res['last_scraped_at']
    if last_scraped:
        ist_scraped = last_scraped + timedelta(hours=5, minutes=30)
        last_scraped_str = ist_scraped.strftime('%Y-%m-%d %H:%M:%S IST')
    else:
        last_scraped_str = "N/A"

    return {
        "total_articles": total,
        "avg_sentiment": avg_s,
        "pos_pct": (pos / total) * 100 if total > 0 else 0.0,
        "neg_pct": (neg / total) * 100 if total > 0 else 0.0,
        "neu_pct": ((total - pos - neg) / total) * 100 if total > 0 else 0.0,
        "last_scraped_at": last_scraped_str
    }

@app.get("/api/sources")
def get_sources_metrics():
    query = """
        SELECT s.source_name, AVG(f.sentiment_score) as avg_sentiment, COUNT(f.article_id) as article_count
        FROM fact_article f
        JOIN dim_source s ON f.source_id = s.source_id
        GROUP BY s.source_name
        ORDER BY s.source_name;
    """
    res = run_db_query(query)
    if res is None:
        return []
    for item in res:
        item['avg_sentiment'] = float(item['avg_sentiment']) if item['avg_sentiment'] is not None else 0.0
    return res

@app.get("/api/keywords")
def get_keywords_metrics():
    query = """
        SELECT k.keyword, COUNT(bk.article_id) as mentions
        FROM bridge_article_keyword bk
        JOIN dim_keyword k ON bk.keyword_id = k.keyword_id
        GROUP BY k.keyword
        ORDER BY mentions DESC
        LIMIT 15;
    """
    res = run_db_query(query)
    return res if res is not None else []

@app.get("/api/trends")
def get_trends_metrics(source: str = None):
    query = """
        SELECT DATE_TRUNC('day', f.published_at) as date, AVG(f.sentiment_score) as avg_sentiment
        FROM fact_article f
    """
    params = []
    if source and source != "All Sources":
        query += " WHERE f.source_id = (SELECT source_id FROM dim_source WHERE source_name = %s)"
        params.append(source)
        
    query += " GROUP BY date ORDER BY date ASC;"
    
    res = run_db_query(query, tuple(params) if params else None)
    if res is None:
        return []
    for item in res:
        item['date'] = item['date'].strftime('%Y-%m-%d')
        item['avg_sentiment'] = float(item['avg_sentiment']) if item['avg_sentiment'] is not None else 0.0
    return res

@app.get("/api/articles")
def get_articles_list(source: str = None, search: str = None):
    query = """
        SELECT 
            f.headline,
            s.source_name,
            f.sentiment_score,
            f.sentiment_label,
            f.published_at,
            f.url
        FROM fact_article f
        JOIN dim_source s ON f.source_id = s.source_id
    """
    conditions = []
    params = []
    
    if source and source != "All Sources":
        conditions.append("s.source_name = %s")
        params.append(source)
    if search:
        conditions.append("f.headline ILIKE %s")
        params.append(f"%{search}%")
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " ORDER BY f.published_at DESC LIMIT 200;"
    
    res = run_db_query(query, tuple(params) if params else None)
    if res is None:
        return []
    for item in res:
        if item.get('published_at'):
            ist_pub = item['published_at'] + timedelta(hours=5, minutes=30)
            item['published_at'] = ist_pub.strftime('%Y-%m-%d %H:%M IST')
        item['sentiment_score'] = float(item['sentiment_score']) if item['sentiment_score'] is not None else 0.0
    return res

# Create frontend folder if not exists
Path("frontend").mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")
