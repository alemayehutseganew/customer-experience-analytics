# Customer Experience Analytics - Week 2

Project scaffold for the 10 Academy Week 2 challenge: scraping, analyzing and visualizing Google Play Store reviews for three Ethiopian banks (CBE, BOA, Dashen).

Overview
- Scripts and notebooks to collect reviews, preprocess, run sentiment and theme analysis, and store data in Postgres.

Quick start
1. Create a Python environment (recommended Python 3.9+).
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Scrape reviews (defaults read from `src/config.py` / `.env`):

```powershell
python src/scrape_reviews.py  # writes to data/raw/reviews_raw.csv

# Scrape a single bank override example
python src/scrape_reviews.py --bank CBE --count 600 --out data/raw/cbe_custom.csv
```

4. Preprocess (cleans and deduplicates into `data/processed/reviews_processed.csv`):

```powershell
python src/preprocess.py
```

5. Sentiment & keywords (outputs `data/processed/reviews_with_sentiment.csv`):

```powershell
python src/sentiment.py
```

6. Insert into Postgres (update the URL or export `PGURL`):

```powershell
set PGURL=postgresql://user:pass@localhost:5432/bank_reviews
python src/db.py
```



Notes
- Configure app ids, language, review counts, and file paths in `src/config.py` or via environment variables (`.env`).
- This scaffold uses `google_play_scraper` (Python package) to collect reviews. If you prefer the Node `google-play-scraper`, see the references in the challenge doc.
- The sentiment script uses VADER by default and will attempt a Hugging Face transformer model if `transformers` is installed.

Branches
- Use `task-1` for scraping/preprocessing work.
- Use `task-2` for sentiment & theme analysis.
- Use `task-3` for DB integration.
- Use `task-4` for final visuals and report.

References
- See the challenge doc for recommended models and libraries.
