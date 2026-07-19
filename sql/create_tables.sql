-- Schema for News Sentiment & Trend Pipeline (Star Schema)

-- 1. Dim Source
CREATE TABLE IF NOT EXISTS dim_source (
    source_id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) UNIQUE NOT NULL,
    base_url VARCHAR(255) NOT NULL
);

-- 2. Dim Keyword
CREATE TABLE IF NOT EXISTS dim_keyword (
    keyword_id SERIAL PRIMARY KEY,
    keyword VARCHAR(100) UNIQUE NOT NULL
);

-- 3. Fact Article
CREATE TABLE IF NOT EXISTS fact_article (
    article_id VARCHAR(64) PRIMARY KEY,
    source_id INT NOT NULL REFERENCES dim_source(source_id) ON DELETE CASCADE,
    headline TEXT NOT NULL,
    summary TEXT,
    url TEXT NOT NULL,
    sentiment_score NUMERIC(5, 4) NOT NULL,
    sentiment_label VARCHAR(20) NOT NULL,
    published_at TIMESTAMP NOT NULL,
    scraped_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. Bridge Article Keyword
CREATE TABLE IF NOT EXISTS bridge_article_keyword (
    article_id VARCHAR(64) REFERENCES fact_article(article_id) ON DELETE CASCADE,
    keyword_id INT REFERENCES dim_keyword(keyword_id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, keyword_id)
);

-- 5. Pipeline Logs
CREATE TABLE IF NOT EXISTS pipeline_logs (
    run_id SERIAL PRIMARY KEY,
    run_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(100),
    status VARCHAR(20) NOT NULL, -- success, fail, partial
    rows_scraped INT DEFAULT 0,
    rows_loaded INT DEFAULT 0,
    error_message TEXT
);
