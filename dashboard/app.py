import streamlit as st
import pandas as pd
import altair as alt
import sys
from pathlib import Path

# Add project root to path for database connection helper
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "src"))

from src.db import get_db_connection

st.set_page_config(
    page_title="News Sentiment & Trend Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling injection
st.markdown("""
<style>
    /* Gradient Main Header */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 30px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        margin: 0;
        font-family: 'Outfit', 'Inter', sans-serif;
        font-size: 2.8rem;
        font-weight: 700;
        letter-spacing: -0.05rem;
    }
    .main-header p {
        margin: 5px 0 0 0;
        font-size: 1.1rem;
        opacity: 0.9;
    }
    
    /* Metrics glassmorphism styling */
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #764ba2;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.05rem;
        color: #555;
    }
    
    /* Custom cards for stats */
    .metric-card {
        background: rgba(255, 255, 255, 0.7);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.3);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Helper to run database queries
def run_query(query, params=None):
    try:
        conn = get_db_connection()
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        # DB might not be ready or tables don't exist yet
        return None

# Check if tables exist
def check_database_ready():
    tables = run_query("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public';
    """)
    if tables is None or len(tables) == 0:
        return False
    # Ensure fact_article is there
    return 'fact_article' in tables['table_name'].values

# Retrieve last scraped timestamp
last_scraped_df = run_query("SELECT MAX(scraped_at) as last_scraped FROM fact_article;")
if last_scraped_df is not None and not last_scraped_df.empty and last_scraped_df['last_scraped'].iloc[0] is not None:
    utc_time = pd.to_datetime(last_scraped_df['last_scraped'].iloc[0])
    ist_time = utc_time + pd.Timedelta(hours=5, minutes=30)
    last_scraped_str = ist_time.strftime('%Y-%m-%d %I:%M:%S %p IST')
else:
    last_scraped_str = "N/A"

st.markdown(f"""
<div class="main-header">
    <h1>News Sentiment & Trend Analytics</h1>
    <p>Real-time updates, sentiment patterns, and keyword trends parsed across HTML & RSS feeds</p>
    <p style="margin-top: 10px; font-weight: 600; opacity: 0.95;">🕒 Last Updated / Scraped: {last_scraped_str}</p>
</div>
""", unsafe_allow_html=True)

db_ready = check_database_ready()

if not db_ready:
    st.warning("⚠️ Database is not initialized or contains no data yet.")
    st.info("The scraping and database loading pipeline needs to run successfully at least once to populate the warehouse. Please check the logs in n8n or trigger the pipeline locally.")
    
    # Show instructions on how to start the pipeline
    st.markdown("""
    ### Quick Start Instructions:
    To manually trigger the ingestion pipeline and see data on this dashboard:
    1. **Scrape headlines:**
       ```bash
       .venv/Scripts/python src/scraper.py
       ```
    2. **Transform & analyze sentiment:**
       ```bash
       .venv/Scripts/python src/transform.py
       ```
    3. **Run Data Quality checks:**
       ```bash
       .venv/Scripts/python src/dq_checks.py
       ```
    4. **Load to PostgreSQL:**
       ```bash
       .venv/Scripts/python src/load.py
       ```
    """)
    st.stop()

# Sidebar controls
st.sidebar.header("⚡ Pipeline Status & Filters")
st.sidebar.markdown("---")

# Retrieve lists for filtering
sources_df = run_query("SELECT source_name FROM dim_source ORDER BY source_name;")
sources_list = ["All Sources"] + sources_df['source_name'].tolist() if sources_df is not None else ["All Sources"]

selected_source = st.sidebar.selectbox("Filter by Source", sources_list)
st.sidebar.markdown("### Active Configuration")
st.sidebar.info(f"• Database: PostgreSQL\n• Scrapers: 2 Sources Active\n• Retention: Last 3 Scraps\n• Last Scraped: {last_scraped_str}")

# 1. Fetch Metrics Summary
query_summary = "SELECT COUNT(*) as total, AVG(sentiment_score) as avg_score FROM fact_article"
if selected_source != "All Sources":
    query_summary += " WHERE source_id = (SELECT source_id FROM dim_source WHERE source_name = %s)"
    metrics = run_query(query_summary, (selected_source,))
else:
    metrics = run_query(query_summary)
total_articles = int(metrics['total'].iloc[0]) if metrics is not None else 0
avg_sentiment = float(metrics['avg_score'].iloc[0]) if metrics is not None and metrics['avg_score'].iloc[0] is not None else 0.0

# Count labels
query_labels = "SELECT sentiment_label, COUNT(*) as count FROM fact_article"
if selected_source != "All Sources":
    query_labels += " WHERE source_id = (SELECT source_id FROM dim_source WHERE source_name = %s)"
    query_labels += " GROUP BY sentiment_label;"
    labels_df = run_query(query_labels, (selected_source,))
else:
    query_labels += " GROUP BY sentiment_label;"
    labels_df = run_query(query_labels)

pos_pct = 0.0
neg_pct = 0.0
neu_pct = 0.0

if labels_df is not None and not labels_df.empty:
    total_lbls = labels_df['count'].sum()
    pos_row = labels_df[labels_df['sentiment_label'] == 'positive']
    neg_row = labels_df[labels_df['sentiment_label'] == 'negative']
    neu_row = labels_df[labels_df['sentiment_label'] == 'neutral']
    
    if not pos_row.empty:
        pos_pct = (pos_row['count'].iloc[0] / total_lbls) * 100
    if not neg_row.empty:
        neg_pct = (neg_row['count'].iloc[0] / total_lbls) * 100
    if not neu_row.empty:
        neu_pct = (neu_row['count'].iloc[0] / total_lbls) * 100

# Render top metrics row
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Scraped Articles", f"{total_articles:,}")
with col2:
    sentiment_emoji = "😊" if avg_sentiment > 0.05 else ("😔" if avg_sentiment < -0.05 else "😐")
    st.metric("Average Sentiment Score", f"{avg_sentiment:.2f} {sentiment_emoji}")
with col3:
    st.metric("Positive Articles", f"{pos_pct:.1f}%")
with col4:
    st.metric("Negative Articles", f"{neg_pct:.1f}%")

st.markdown("---")

# Layout: 2 Columns for Charts
chart_col1, chart_col2 = st.columns([1, 1])

with chart_col1:
    st.subheader("📊 Sentiment Score by Source")
    source_stats_query = """
        SELECT s.source_name, AVG(f.sentiment_score) as avg_sentiment, COUNT(f.article_id) as count
        FROM fact_article f
        JOIN dim_source s ON f.source_id = s.source_id
        GROUP BY s.source_name;
    """
    source_stats = run_query(source_stats_query)
    
    if source_stats is not None and not source_stats.empty:
        chart_source = alt.Chart(source_stats).mark_bar().encode(
            x=alt.X('source_name:N', title='Source'),
            y=alt.Y('avg_sentiment:Q', title='Average Sentiment Score'),
            color=alt.Color('avg_sentiment:Q', scale=alt.Scale(scheme='purples'), legend=None),
            tooltip=['source_name', 'avg_sentiment', 'count']
        ).properties(height=350)
        st.altair_chart(chart_source, use_container_width=True)
    else:
        st.write("No source statistics available.")

with chart_col2:
    st.subheader("🔑 Top Trending Keywords")
    keyword_query = """
        SELECT k.keyword, COUNT(bk.article_id) as mentions
        FROM bridge_article_keyword bk
        JOIN dim_keyword k ON bk.keyword_id = k.keyword_id
        GROUP BY k.keyword
        ORDER BY mentions DESC
        LIMIT 10;
    """
    keyword_stats = run_query(keyword_query)
    
    if keyword_stats is not None and not keyword_stats.empty:
        chart_keywords = alt.Chart(keyword_stats).mark_bar(cornerRadiusTopRight=5).encode(
            x=alt.X('mentions:Q', title='Mentions'),
            y=alt.Y('keyword:N', sort='-x', title='Keyword'),
            color=alt.Color('mentions:Q', scale=alt.Scale(scheme='tealblues'), legend=None),
            tooltip=['keyword', 'mentions']
        ).properties(height=350)
        st.altair_chart(chart_keywords, use_container_width=True)
    else:
        st.write("No keyword statistics available.")

st.markdown("---")

# Sentiment Trend over Time
st.subheader("📈 Average Sentiment Trend")
trend_query = """
    SELECT DATE_TRUNC('day', published_at) as date, AVG(sentiment_score) as avg_sentiment
    FROM fact_article
    GROUP BY date
    ORDER BY date ASC;
"""
trend_df = run_query(trend_query)
if trend_df is not None and not trend_df.empty:
    trend_df['date'] = pd.to_datetime(trend_df['date'])
    chart_trend = alt.Chart(trend_df).mark_line(point=True, color="#764ba2").encode(
        x=alt.X('date:T', title='Publish Date'),
        y=alt.Y('avg_sentiment:Q', title='Avg Sentiment Score'),
        tooltip=['date:T', 'avg_sentiment:Q']
    ).properties(height=300)
    st.altair_chart(chart_trend, use_container_width=True)
else:
    st.write("No trend data available.")

st.markdown("---")

# Article Explorer Section
st.subheader("🔍 Explore Articles")

articles_query = """
    SELECT 
        f.published_at as "Publish Date",
        s.source_name as "Source",
        f.headline as "Headline",
        f.sentiment_score as "Score",
        f.sentiment_label as "Label",
        f.url as "URL"
    FROM fact_article f
    JOIN dim_source s ON f.source_id = s.source_id
"""
if selected_source != "All Sources":
    articles_query += " WHERE s.source_name = %s"
    articles_query += " ORDER BY f.published_at DESC LIMIT 200;"
    articles_df = run_query(articles_query, (selected_source,))
else:
    articles_query += " ORDER BY f.published_at DESC LIMIT 200;"
    articles_df = run_query(articles_query)

if articles_df is not None and not articles_df.empty:
    # Styling and formatting before displaying in IST (12-hour AM/PM)
    articles_df['Publish Date'] = (pd.to_datetime(articles_df['Publish Date']) + pd.Timedelta(hours=5, minutes=30)).dt.strftime('%Y-%m-%d %I:%M %p IST')
    
    # Set search input
    search_query = st.text_input("Search headlines...", "")
    if search_query:
        articles_df = articles_df[articles_df['Headline'].str.contains(search_query, case=False)]
        
    st.dataframe(
        articles_df,
        column_config={
            "URL": st.column_config.LinkColumn("Article Link", display_text="Open Article"),
            "Score": st.column_config.NumberColumn("Score", format="%.2f"),
        },
        use_container_width=True,
        hide_index=True
    )
else:
    st.write("No articles found matching filters.")
