"""
Configuration file for Bank Reviews Analysis Project
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Google Play Store App IDs
APP_IDS = {
# env
    'CBE': os.getenv('CBE_APP_ID', 'com.combanketh.mobilebanking'),
    'Abissinia': os.getenv('ABSSINIA_APP_ID', 'com.boa.boaMobileBanking'),
    'Dashen': os.getenv('DASHEN_APP_ID', 'com.dashen.dashensuperapp')

}

# Bank Names Mapping
BANK_NAMES = {
    'CBE': 'Commercial Bank of Ethiopia',
    'Abissinia': 'Abissinia Bank',
    'Dashen': 'Dashen Bank'
}

# Scraping Configuration
SCRAPING_CONFIG = {
    'reviews_per_bank': int(os.getenv('REVIEWS_PER_BANK', 800)),
    'max_retries': int(os.getenv('MAX_RETRIES', 3)),
    'lang': 'en',
    'country': 'et'  # Ethiopia
}

# Data quality guardrails
_MIN_REVIEWS_PER_BANK = int(os.getenv('MIN_REVIEWS_PER_BANK', 400))
_MIN_TOTAL_REVIEWS = int(os.getenv('MIN_TOTAL_REVIEWS', len(BANK_NAMES) * _MIN_REVIEWS_PER_BANK))
_MAX_MISSING_RATIO = float(os.getenv('MAX_MISSING_RATIO', 0.05))
_MAX_DROP_RATIO = float(os.getenv('MAX_DROP_RATIO', 0.4))

QUALITY_THRESHOLDS = {
    'min_reviews_per_bank': _MIN_REVIEWS_PER_BANK,
    'min_total_reviews': _MIN_TOTAL_REVIEWS,
    'max_missing_ratio': _MAX_MISSING_RATIO,
    'max_drop_ratio': _MAX_DROP_RATIO,
}

# File Paths
DATA_PATHS = {
    'raw': 'data/raw',
    'processed': 'data/processed',
    'raw_reviews': 'data/raw/reviews_raw.csv',
    'processed_reviews': 'data/processed/reviews_processed.csv',
    'sentiment_results': 'data/processed/reviews_with_sentiment.csv',
    'final_results': 'data/processed/reviews_final.csv'
}

# Database Configuration
DB_URL = os.getenv('PGURL') or os.getenv('DATABASE_URL') or 'postgresql://postgres:postgres@localhost:5432/bank_reviews'









