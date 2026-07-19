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

def analyze_sentiment(analyzer, text: str):
    scores = analyzer.polarity_scores(text)
    compound = scores['compound']
    
    if compound >= 0.05:
        label = 'positive'
    elif compound <= -0.05:
        label = 'negative'
    else:
        label = 'neutral'
        
    return compound, label

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
    processed_records = []
    
    for art in deduped_articles:
        # sentiment
        score, label = analyze_sentiment(analyzer, art['headline'])
        art['sentiment_score'] = score
        art['sentiment_label'] = label
        
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
