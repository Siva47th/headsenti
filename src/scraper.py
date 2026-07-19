import os
import sys
import json
import yaml
import hashlib
from datetime import datetime
from pathlib import Path
import feedparser
from playwright.sync_api import sync_playwright

# Add current directory and src directory to sys.path to ensure correct imports
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent))

from schema import Article

def get_hash(source: str, headline: str, date_str: str) -> str:
    combined = f"{source}:{headline}:{date_str}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

def scrape_html_source(source_cfg):
    articles = []
    source_name = source_cfg['name']
    url = source_cfg['url']
    row_sel = source_cfg['row_selector']
    headline_sel = source_cfg['headline_selector']
    link_sel = source_cfg['link_selector']
    
    print(f"Scraping HTML source: {source_name} from {url}")
    with sync_playwright() as p:
        exec_path = os.getenv("PLAYWRIGHT_CHROME_EXECUTABLE_PATH")
        if exec_path:
            print(f"Using system chromium: {exec_path}")
            browser = p.chromium.launch(headless=True, executable_path=exec_path)
        else:
            browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        
        # Locate rows
        rows = page.locator(row_sel).all()
        print(f"Found {len(rows)} matching rows for {source_name}")
        
        for i, row in enumerate(rows):
            try:
                # Extract headline
                hl_el = row.locator(headline_sel).first
                if not hl_el.count():
                    continue
                headline = hl_el.inner_text().strip()
                
                # Extract link
                link_el = row.locator(link_sel).first
                link = link_el.get_attribute("href")
                if link and not link.startswith("http"):
                    from urllib.parse import urljoin
                    link = urljoin(url, link)
                
                # Extract date
                date_str = None
                date_sel = source_cfg.get('date_selector')
                if date_sel:
                    if date_sel.startswith("+ tr"):
                        sub_sel = date_sel.replace("+ tr", "").strip()
                        date_el = row.locator("xpath=following-sibling::tr[1]").locator(sub_sel).first
                    else:
                        date_el = row.locator(date_sel).first
                    
                    if date_el.count():
                        attr = source_cfg.get('date_attribute')
                        if attr:
                            date_str = date_el.get_attribute(attr)
                        else:
                            date_str = date_el.inner_text().strip()
                
                # Parse date or default to now
                if date_str:
                    try:
                        # Clean if format has timezone offset Z or contains extra tokens
                        date_str = date_str.split()[0]
                        if date_str.endswith('Z'):
                            date_str = date_str[:-1]
                        published_at = datetime.fromisoformat(date_str)
                    except Exception as e:
                        print(f"Error parsing date {date_str}: {e}. Using current time.")
                        published_at = datetime.utcnow()
                else:
                    published_at = datetime.utcnow()
                
                if not headline or not link:
                    continue
                
                art_id = get_hash(source_name, headline, published_at.isoformat())
                
                article_data = {
                    "article_id": art_id,
                    "source_name": source_name,
                    "headline": headline,
                    "summary": None,
                    "url": link,
                    "published_at": published_at.isoformat(),
                    "scraped_at": datetime.utcnow().isoformat()
                }
                
                art = Article(**article_data)
                articles.append(art.model_dump(mode='json'))
            except Exception as e:
                print(f"Error processing row {i} for {source_name}: {e}")
                
        browser.close()
    return articles

def scrape_rss_source(source_cfg):
    articles = []
    source_name = source_cfg['name']
    url = source_cfg['url']
    
    print(f"Scraping RSS source: {source_name} from {url}")
    feed = feedparser.parse(url)
    print(f"Found {len(feed.entries)} entries for {source_name}")
    
    for entry in feed.entries:
        try:
            headline = entry.get('title', '').strip()
            link = entry.get('link', '').strip()
            summary = entry.get('summary', entry.get('description', ''))
            
            if not headline or not link:
                continue
                
            published_parsed = entry.get('published_parsed')
            if published_parsed:
                published_at = datetime(*published_parsed[:6])
            else:
                published_at = datetime.utcnow()
                
            art_id = get_hash(source_name, headline, published_at.isoformat())
            
            article_data = {
                "article_id": art_id,
                "source_name": source_name,
                "headline": headline,
                "summary": summary,
                "url": link,
                "published_at": published_at.isoformat(),
                "scraped_at": datetime.utcnow().isoformat()
            }
            
            art = Article(**article_data)
            articles.append(art.model_dump(mode='json'))
        except Exception as e:
            print(f"Error processing RSS entry for {source_name}: {e}")
            
    return articles

def main():
    config_path = Path("config/sources.yaml")
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)
        
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    sources = config.get('sources', [])
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    output_dir = Path("data/raw") / today_str
    output_dir.mkdir(parents=True, exist_ok=True)
    
    overall_success = True
    scraped_count = 0
    
    for source_cfg in sources:
        name = source_cfg.get('name')
        stype = source_cfg.get('type')
        try:
            if stype == 'html':
                articles = scrape_html_source(source_cfg)
            elif stype == 'rss':
                articles = scrape_rss_source(source_cfg)
            else:
                print(f"Unknown source type: {stype} for {name}")
                continue
                
            output_file = output_dir / f"{name}.json"
            with open(output_file, 'w', encoding='utf-8') as out:
                json.dump(articles, out, indent=2, ensure_ascii=False)
                
            print(f"Successfully saved {len(articles)} articles to {output_file}")
            scraped_count += len(articles)
        except Exception as e:
            print(f"Failed to scrape source {name}: {e}")
            overall_success = False
            
    print(f"Pipeline scrape step completed. Total scraped: {scraped_count}")
    if not overall_success:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
