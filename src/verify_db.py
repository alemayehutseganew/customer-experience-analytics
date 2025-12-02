"""
Verification script to check data integrity in PostgreSQL.
Runs aggregate SQL checks and logs results.
"""
import logging
import os
import pandas as pd
from sqlalchemy import create_engine, text
from config import DB_URL

logging.basicConfig(level=os.getenv('LOGLEVEL', 'INFO'), format='[%(levelname)s] %(message)s')
LOGGER = logging.getLogger(__name__)

def verify_data():
    LOGGER.info(f"Connecting to database: {DB_URL}")
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            # 1. Total Count
            result = conn.execute(text("SELECT COUNT(*) FROM reviews")).scalar()
            LOGGER.info(f"Total reviews in DB: {result}")

            # 2. Aggregates per Bank
            query = """
            SELECT 
                b.bank_name, 
                COUNT(r.review_id) as count, 
                AVG(r.rating) as avg_rating,
                AVG(r.sentiment_score) as avg_sentiment
            FROM reviews r
            JOIN banks b ON r.bank_id = b.bank_id
            GROUP BY b.bank_name
            ORDER BY avg_rating DESC
            """
            df = pd.read_sql(query, conn)
            LOGGER.info("\nPer-Bank Stats:\n" + df.to_string(index=False))
            
            # 3. Check for Nulls in critical fields
            null_check = conn.execute(text("SELECT COUNT(*) FROM reviews WHERE review_text IS NULL OR rating IS NULL")).scalar()
            if null_check > 0:
                LOGGER.warning(f"Found {null_check} rows with NULL review_text or rating!")
            else:
                LOGGER.info("Data Integrity Check: No NULLs in critical columns.")

    except Exception as e:
        LOGGER.error(f"Verification failed: {e}")

if __name__ == "__main__":
    verify_data()
