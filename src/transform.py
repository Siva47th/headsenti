import os
import sys
import json
import re
import argparse
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory and src directory to sys.path to ensure correct imports
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent))

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", "of", "from", 
    "as", "is", "are", "was", "were", "be", "been", "has", "have", "had", "do", "does", "did", 
    "this", "that", "these", "those", "it", "its", "i", "you", "he", "she", "they", "we", "us", 
    "them", "my", "your", "his", "her", "their", "our", "about", "into", "through", "during", 
    "before", "after", "above", "below", "up", "down", "in", "out", "off", "over", "under", "again", 
    "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "any", 
    "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", 
    "own", "same", "so", "than", "too", "very", "can", "will", "just", "should", "now"
}

def clean_text(text: str) -> str:
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def are_similar(h1: str, h2: str, threshold: float = 0.85) -> bool:
    return SequenceMatcher(None, h1.lower(), h2.lower()).ratio() >= threshold

def deduplicate_articles(articles, threshold=0.85):
    deduped = []
    for art in articles:
        is_dup = False
        for existing in deduped:
            if are_similar(art['headline'], existing['headline'], threshold):
                # Print info about duplicate removal
                print(f"Removing duplicate headline:\n  -> '{art['headline']}'\n  Similar to: '{existing['headline']}'")
                is_dup = True
                break
        if not is_dup:
            deduped.append(art)
    return deduped

def extract_keywords(headline: str, limit: int = 5) -> list:
    # Remove punctuation
    cleaned = re.sub(r'[^\w\s]', '', headline.lower())
    words = cleaned.split()
    # Filter stopwords and numeric tokens
    filtered = [w for w in words if w not in STOPWORDS and len(w) > 2 and not w.isdigit()]
    
    unique_words = []
    for w in filtered:
        if w not in unique_words:
            unique_words.append(w)
            if len(unique_words) >= limit:
                break
    return unique_words

import time

def analyze_sentiment_batch(analyzer, articles, gemini_client=None):
    if not gemini_client:
        # Fallback to VADER for all articles
        for art in articles:
            scores = analyzer.polarity_scores(art['headline'])
            compound = scores['compound']
            art['sentiment_score'] = compound
            art['sentiment_label'] = 'positive' if compound >= 0.05 else ('negative' if compound <= -0.05 else 'neutral')
        return
        
    print(f"Starting Gemini batch sentiment analysis on {len(articles)} articles...")
    batch_size = 15
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i+batch_size]
        headlines_list = [{"id": idx, "headline": art['headline']} for idx, art in enumerate(batch)]
        
        try:
            prompt = (
                "You are a professional sentiment analysis model. "
                "Analyze the sentiment of each of the following news headlines. "
                "Output exactly a JSON list of objects in this format (no other text, just the raw JSON list):\n"
                '[\n  {"id": 0, "score": 0.85, "label": "positive"},\n  {"id": 1, "score": -0.6, "label": "negative"}\n]\n\n'
                f"Headlines to analyze:\n{json.dumps(headlines_list)}\n\n"
                "Note: the score must be a number between -1.0 (most negative) and 1.0 (most positive). "
                "The label must be 'positive' (score >= 0.05), 'negative' (score <= -0.05), or 'neutral' otherwise. "
                "Match the 'id' of each object in the input exactly in the output."
            )
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            txt = response.text.strip()
            
            # Strip markdown code blocks if the model wrapped the JSON
            if txt.startswith("```json"):
                txt = txt.split("```json")[1].split("```")[0].strip()
            elif txt.startswith("```"):
                txt = txt.split("```")[1].split("```")[0].strip()
                
            results = json.loads(txt)
            results_map = {res['id']: res for res in results if 'id' in res}
            
            for idx, art in enumerate(batch):
                if idx in results_map:
                    art['sentiment_score'] = float(results_map[idx].get('score', 0.0))
                    art['sentiment_label'] = str(results_map[idx].get('label', 'neutral')).lower()
                else:
                    # fallback single VADER if missing from batch results
                    scores = analyzer.polarity_scores(art['headline'])
                    art['sentiment_score'] = scores['compound']
                    art['sentiment_label'] = 'positive' if scores['compound'] >= 0.05 else ('negative' if scores['compound'] <= -0.05 else 'neutral')
            print(f"Processed batch {i // batch_size + 1}/{(len(articles) - 1) // batch_size + 1} with Gemini.")
        except Exception as e:
            print(f"Gemini batch sentiment analysis failed: {e}. Falling back to VADER for this batch.")
            for art in batch:
                scores = analyzer.polarity_scores(art['headline'])
                compound = scores['compound']
                art['sentiment_score'] = compound
                art['sentiment_label'] = 'positive' if compound >= 0.05 else ('negative' if compound <= -0.05 else 'neutral')
                
        # Sleep 4 seconds between batches to avoid any rate limit spikes
        if i + batch_size < len(articles):
            time.sleep(4.0)

def main():
    parser = argparse.ArgumentParser(description="Transform and clean raw scraped news articles.")
    parser.add_argument('--date', type=str, help="Date folder to process (YYYY-MM-DD). Defaults to today.")
    args = parser.parse_args()
    
    date_str = args.date if args.date else datetime.utcnow().strftime('%Y-%m-%d')
    raw_dir = Path("data/raw") / date_str
    staging_dir = Path("data/staging") / date_str
    
    if not raw_dir.exists():
        print(f"Raw data directory does not exist: {raw_dir}")
        sys.exit(1)
        
    # Read all JSON files in the raw directory
    all_articles = []
    for json_file in raw_dir.glob("*.json"):
        print(f"Reading raw data from: {json_file}")
        with open(json_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                all_articles.extend(data)
            except Exception as e:
                print(f"Error reading {json_file}: {e}")
                
    if not all_articles:
        print("No articles found to process.")
        sys.exit(0)
        
    print(f"Total articles loaded: {len(all_articles)}")
    
    # 1. Clean Text
    for art in all_articles:
        art['headline'] = clean_text(art['headline'])
        if art.get('summary'):
            art['summary'] = clean_text(art['summary'])
            
    # 2. Deduplicate
    deduped_articles = deduplicate_articles(all_articles, threshold=0.85)
    print(f"Articles after deduplication: {len(deduped_articles)}")
    
    # 3. Sentiment Analysis and Keyword Extraction
    analyzer = SentimentIntensityAnalyzer()
    
    # Initialize Gemini client if key is configured
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_client = None
    if gemini_key:
        try:
            gemini_client = genai.Client(api_key=gemini_key)
            print("Gemini API Client initialized for sentiment analysis.")
        except Exception as e:
            print(f"Failed to configure Gemini API Client: {e}")
            
    processed_records = []
    
    # Batch run sentiment analysis (populates 'sentiment_score' and 'sentiment_label' in place)
    analyze_sentiment_batch(analyzer, deduped_articles, gemini_client)
    
    processed_records = []
    for art in deduped_articles:
        # keywords
        art['keywords'] = extract_keywords(art['headline'])
        processed_records.append(art)
        
    # Create DataFrame
    df = pd.DataFrame(processed_records)
    
    # Ensure types are correct
    df['published_at'] = pd.to_datetime(df['published_at'])
    df['scraped_at'] = pd.to_datetime(df['scraped_at'])
    df['sentiment_score'] = df['sentiment_score'].astype(float)
    
    # Create staging folder and write Parquet
    staging_dir.mkdir(parents=True, exist_ok=True)
    output_file = staging_dir / "articles_clean.parquet"
    
    df.to_parquet(output_file, index=False)
    print(f"Successfully transformed and saved staging data to: {output_file}")
    sys.exit(0)

if __name__ == '__main__':
    main()
