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

3. Scrape reviews:

```powershell
# CBE
python src/scrape_reviews.py --package com.combanketh.mobilebanking --bank "CBE" --count 500 --out data/raw/cbe_reviews.csv

# BOA
python src/scrape_reviews.py --package com.boa.boaMobileBanking --bank "BOA" --count 500 --out data/raw/boa_reviews.csv

# Dashen
python src/scrape_reviews.py --package com.dashen.dashensuperapp --bank "Dashen" --count 500 --out data/raw/dashen_reviews.csv
```

4. Preprocess:

```powershell
python src/preprocess.py --in data/raw/cbe_reviews.csv --out data/clean/cbe_reviews.csv
python src/preprocess.py --in data/raw/boa_reviews.csv --out data/clean/boa_reviews.csv
python src/preprocess.py --in data/raw/dashen_reviews.csv --out data/clean/dashen_reviews.csv
```

5. Sentiment & themes:

```powershell
python src/sentiment.py --in data/clean/cbe_reviews.csv --out data/annotated/cbe_reviews.csv
python src/sentiment.py --in data/clean/boa_reviews.csv --out data/annotated/boa_reviews.csv
python src/sentiment.py --in data/clean/dashen_reviews.csv --out data/annotated/dashen_reviews.csv
```

6. Insert into Postgres (update connection URL inside `src/db.py` or pass via env var):



Notes
- This scaffold uses `google_play_scraper` (Python package) to collect reviews. If you prefer the Node `google-play-scraper`, see the references in the challenge doc.
- The sentiment script uses VADER by default and will attempt a Hugging Face transformer model if `transformers` is installed.

Branches
- Use `task-1` for scraping/preprocessing work.
- Use `task-2` for sentiment & theme analysis.
- Use `task-3` for DB integration.
- Use `task-4` for final visuals and report.

References
- See the challenge doc for recommended models and libraries.
