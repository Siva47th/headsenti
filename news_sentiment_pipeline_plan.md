# News Sentiment & Trend Pipeline
## Full Implementation Plan (Playwright + n8n + Python + Data Engineering)

---

## 1. Project Goal

Build an end-to-end data pipeline that:
- Scrapes news headlines/articles from multiple sources on a schedule
- Cleans and validates the data
- Runs sentiment analysis on each article
- Loads everything into a structured Postgres warehouse (fact/dimension model)
- Detects trends (sentiment shifts, spiking keywords)
- Sends automated digest alerts
- Optionally visualizes trends on a dashboard

**Stack:** Python, Playwright, Pydantic, Pandas, VADER, PostgreSQL, n8n, Docker, Streamlit (optional)
**Cost:** $0 — everything is open-source and self-hosted.

---

## 2. High-Level Architecture

```
                ┌─────────────────────┐
                │   n8n (Cron 6h)      │  ORCHESTRATION
                └──────────┬───────────┘
                           │ triggers
                           ▼
                ┌─────────────────────┐
                │  scraper.py          │  EXTRACTION (Playwright)
                │  (loops per source)  │
                └──────────┬───────────┘
                           ▼
                data/raw/<date>/<source>.json   (LANDING ZONE)
                           │
                           ▼
                ┌─────────────────────┐
                │  validate.py         │  Pydantic schema check
                └──────────┬───────────┘
                           ▼
                ┌─────────────────────┐
                │  transform.py         │  TRANSFORMATION
                │  - clean text          │
                │  - dedupe               │
                │  - sentiment (VADER)     │
                │  - keyword extraction     │
                └──────────┬───────────┘
                           ▼
                data/staging/<date>/articles_clean.parquet  (STAGING)
                           │
                           ▼
                ┌─────────────────────┐
                │  dq_checks.py         │  DATA QUALITY GATE
                └──────────┬───────────┘
                    pass ──┴── fail → n8n alert, pipeline stops
                           ▼
                ┌─────────────────────┐
                │  load.py              │  LOAD (incremental)
                └──────────┬───────────┘
                           ▼
                ┌─────────────────────┐
                │   PostgreSQL          │  CURATED WAREHOUSE
                │   (star schema)        │
                └──────────┬───────────┘
                           ▼
                ┌─────────────────────┐
                │  n8n Postgres node    │  ANALYTICS + ALERTS
                │  runs trend SQL        │
                │  → Slack/Telegram      │
                └─────────────────────┘
                           │
                           ▼ (optional)
                ┌─────────────────────┐
                │  Streamlit dashboard  │
                └─────────────────────┘
```

---

## 3. Folder Structure

```
news-pipeline/
├── docker-compose.yml
├── .env
├── requirements.txt
├── config/
│   └── sources.yaml          # list of news sources + selectors
├── src/
│   ├── scraper.py
│   ├── schema.py              # Pydantic models
│   ├── validate.py
│   ├── transform.py
│   ├── sentiment.py
│   ├── dq_checks.py
│   ├── load.py
│   └── db.py                  # DB connection helper
├── sql/
│   ├── create_tables.sql
│   └── trend_queries.sql
├── data/
│   ├── raw/
│   ├── staging/
│   └── logs/
├── dashboard/
│   └── app.py                 # Streamlit (optional)
└── n8n/
    └── news_pipeline_workflow.json
```

---

## 4. Data Model (Star Schema)

**dim_source**
| column | type |
|---|---|
| source_id (PK) | serial |
| source_name | text |
| base_url | text |

**dim_keyword**
| column | type |
|---|---|
| keyword_id (PK) | serial |
| keyword | text unique |

**fact_article**
| column | type |
|---|---|
| article_id (PK) | text (hash of source+headline+date) |
| source_id (FK) | int |
| headline | text |
| summary | text |
| url | text |
| sentiment_score | float |
| sentiment_label | text (positive/neutral/negative) |
| published_at | timestamp |
| scraped_at | timestamp |

**bridge_article_keyword**
| column | type |
|---|---|
| article_id (FK) | text |
| keyword_id (FK) | int |

**pipeline_logs**
| column | type |
|---|---|
| run_id (PK) | serial |
| run_time | timestamp |
| source | text |
| status | text (success/fail/partial) |
| rows_scraped | int |
| rows_loaded | int |
| error_message | text |

`article_id` = `hash(source_name + headline + published_date)` → this is your **idempotency key**, so re-running the pipeline never creates duplicates.

---

## 5. Build Phases (Suggested Timeline)

### Phase 0 — Environment Setup (Day 1)
- Install Python 3.11+, Docker Desktop
- `pip install playwright pydantic pandas vaderSentiment psycopg2-binary pyyaml streamlit`
- `playwright install` (downloads browser binaries)
- Spin up Postgres + n8n via Docker Compose (below)

### Phase 1 — Single-Source Scraper (Day 2–3)
- Build `scraper.py` for **one** source only
- Print scraped data to console, no storage yet
- Handle: page load waits, pagination, error handling if selectors break

### Phase 2 — Schema & Validation (Day 3)
- Define `Article` Pydantic model in `schema.py`
- Validate scraped output; log/skip malformed records
- Save valid records as raw JSON with timestamp

### Phase 3 — Multi-Source Config (Day 4)
- Move source-specific selectors into `config/sources.yaml`
- Refactor scraper to loop over sources generically
- Wrap each source scrape in try/except so one broken source doesn't kill the run (partial failure resilience)

### Phase 4 — Transformation + Sentiment (Day 5–6)
- Clean text (strip HTML tags, whitespace, special chars)
- Dedupe near-identical headlines across sources (`difflib.SequenceMatcher`)
- Run VADER sentiment → `compound` score → label (positive/neutral/negative)
- Extract keywords (simple frequency-based or a fixed watch-list of topics)
- Save to staging as Parquet

### Phase 5 — Data Quality Gate (Day 6)
- No null headlines
- sentiment_score in [-1, 1]
- No duplicate `article_id`
- Fail loudly (non-zero exit code) if any check fails — n8n reads this

### Phase 6 — Database + Load (Day 7–8)
- Run `sql/create_tables.sql` against Postgres
- Write `load.py`: upsert into `dim_source`, `dim_keyword`; insert new rows into `fact_article` and bridge table only if `article_id` doesn't already exist (incremental load)
- Log every run into `pipeline_logs`

### Phase 7 — n8n Orchestration (Day 9)
- Build the workflow (details in Section 8)
- Test manual trigger first, then enable Cron

### Phase 8 — Analytics + Alerts (Day 10)
- Write trend SQL queries (Section 7)
- Wire n8n Postgres node → Slack/Telegram/Email digest

### Phase 9 — Dashboard (Optional, Day 11–12)
- Streamlit app reading from Postgres: sentiment over time chart, top keywords, source comparison

### Phase 10 — Polish for Portfolio (Day 13)
- README with architecture diagram
- Sample screenshots of alerts + dashboard
- Push to GitHub, write a short blog post/LinkedIn post explaining the design decisions

**Total: ~2 weeks part-time, faster if full-time.**

---

## 6. Docker Compose (Postgres + n8n)

```yaml
version: "3.8"
services:
  postgres:
    image: postgres:16
    restart: always
    environment:
      POSTGRES_USER: newsuser
      POSTGRES_PASSWORD: newspass
      POSTGRES_DB: news_pipeline
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  n8n:
    image: n8nio/n8n
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=changeme
    volumes:
      - n8n_data:/home/node/.n8n
      - ./:/home/node/project   # mount your project so n8n's Execute Command node can run your scripts

volumes:
  pgdata:
  n8n_data:
```

Run with: `docker compose up -d`
n8n UI → `http://localhost:5678`

---

## 7. Trend SQL Queries (used by n8n for alerts/reports)

**Average sentiment by source (last 24h)**
```sql
SELECT s.source_name, AVG(f.sentiment_score) AS avg_sentiment, COUNT(*) AS article_count
FROM fact_article f
JOIN dim_source s ON f.source_id = s.source_id
WHERE f.scraped_at >= NOW() - INTERVAL '24 hours'
GROUP BY s.source_name
ORDER BY avg_sentiment ASC;
```

**Sentiment shift vs previous period (spike detection)**
```sql
WITH current_period AS (
  SELECT AVG(sentiment_score) AS avg_now
  FROM fact_article WHERE scraped_at >= NOW() - INTERVAL '24 hours'
),
previous_period AS (
  SELECT AVG(sentiment_score) AS avg_prev
  FROM fact_article
  WHERE scraped_at >= NOW() - INTERVAL '48 hours'
    AND scraped_at < NOW() - INTERVAL '24 hours'
)
SELECT avg_now, avg_prev, (avg_now - avg_prev) AS shift
FROM current_period, previous_period;
```

**Top trending keywords (last 24h)**
```sql
SELECT k.keyword, COUNT(*) AS mentions
FROM bridge_article_keyword bk
JOIN dim_keyword k ON bk.keyword_id = k.keyword_id
JOIN fact_article f ON bk.article_id = f.article_id
WHERE f.scraped_at >= NOW() - INTERVAL '24 hours'
GROUP BY k.keyword
ORDER BY mentions DESC
LIMIT 10;
```

---

## 8. n8n Workflow Design

**Nodes, in order:**

1. **Cron Trigger** — every 6 hours
2. **Execute Command** — `python src/scraper.py` → exits non-zero on total failure
3. **IF** — check exit code
   - Fail branch → **Slack/Email node**: "Scrape failed" + log tail
4. **Execute Command** — `python src/transform.py`
5. **Execute Command** — `python src/dq_checks.py`
6. **IF** — check DQ exit code
   - Fail branch → **Slack/Email node**: "Data quality check failed" + reason
7. **Execute Command** — `python src/load.py`
8. **Postgres Node** — run trend SQL queries (Section 7)
9. **Function Node** — format results into a readable digest message
10. **Slack / Telegram / Email Node** — send the daily/6-hourly digest

**Error handling tip:** each Python script should `sys.exit(1)` on failure and print a clear error to stdout/stderr — n8n's Execute Command node captures this in its output, which you can pass into the alert message via an expression like `{{$json.stderr}}`.

---

## 9. Data Quality Checks (dq_checks.py logic)

```python
def run_checks(df):
    errors = []
    if df['headline'].isnull().any():
        errors.append("Null headlines found")
    if not df['sentiment_score'].between(-1, 1).all():
        errors.append("Sentiment score out of range")
    if df['article_id'].duplicated().any():
        errors.append("Duplicate article_id found")
    if len(df) == 0:
        errors.append("Zero rows in this batch")

    if errors:
        for e in errors:
            print(f"DQ FAILURE: {e}")
        sys.exit(1)
    print(f"DQ PASSED: {len(df)} rows validated")
```

---

## 10. Key Data Engineering Concepts Reinforced

| Concept | Where it appears |
|---|---|
| Landing / Raw / Staging / Curated zones | Folder structure + Postgres split |
| Schema-on-write validation | Pydantic model before anything moves downstream |
| Idempotency | `article_id` hash prevents duplicate loads on reruns |
| Incremental loading | Load script only inserts unseen `article_id`s |
| Partial failure resilience | One broken source doesn't kill the whole run |
| Star schema modeling | fact_article + dim_source + dim_keyword + bridge table |
| Data quality gates | dq_checks.py blocks bad data from reaching curated layer |
| Orchestration & retries | n8n Cron + IF branching + alerting |
| Observability | pipeline_logs table + n8n failure alerts |
| Trend/time-series analytics | SQL window comparisons (24h vs previous 24h) |

---

## 11. Legal/Ethical Note on Sources

- Check `robots.txt` of any site before scraping
- Prefer sites with public RSS feeds where possible (fully legal, and you can still use Playwright for 1–2 sources that don't have RSS, to keep showcasing scraping skills)
- For pure practice while building, use scrape-friendly sandbox sites first, then swap in real sources once your pipeline logic is solid

---

## 12. What to Show in Your Portfolio/README

- Architecture diagram (the one in Section 2)
- A GIF/screenshot of the n8n workflow running
- A screenshot of a Slack/Telegram alert
- A screenshot of the Streamlit dashboard (if built)
- A short write-up: "Why I designed it this way" — mention idempotency, star schema, DQ gates, partial failure handling specifically, since these are the parts that signal real data engineering thinking, not just scripting

---

## Next Step

Start with **Phase 0 + Phase 1**: environment setup and a single-source Playwright scraper. Once that's working and printing clean data to console, everything else builds on top of it incrementally.
