"""Scrape Google Play reviews for the banks configured in ``config.py``.

The script can scrape all banks defined in :data:`config.APP_IDS` or a specific bank via
the ``--bank`` CLI argument. Output paths, languages, and review counts default to
values declared inside ``config.py`` so that changes can be centralized in one place.
"""
import argparse
import os
from datetime import datetime
from typing import Dict, Iterable, List

import pandas as pd
from google_play_scraper import Sort, reviews

from config import APP_IDS, BANK_NAMES, DATA_PATHS, SCRAPING_CONFIG

SOURCE = 'google_play'


def _serialize_review(bank_code: str, package: str, payload: dict) -> dict:
    """Normalize the review payload we get from google-play-scraper."""
    text = (payload.get('content') or payload.get('review') or '').strip()
    rating = payload.get('score') or payload.get('rating')
    date_value = payload.get('at') or payload.get('date')
    if isinstance(date_value, datetime):
        date_value = date_value.date().isoformat()
    elif date_value:
        date_value = str(date_value)

    return {
        'bank_code': bank_code,
        'bank': BANK_NAMES.get(bank_code, bank_code),
        'package': package,
        'review': text,
        'rating': rating,
        'date': date_value,
        'source': SOURCE,
    }


def scrape_bank(bank_code: str, package_name: str, *, lang: str, country: str, count: int) -> List[dict]:
    """Scrape a single bank/app id and return serialized reviews."""
    collected = []
    continuation_token = None
    chunk = min(200, count)

    while len(collected) < count:
        batch, continuation_token = reviews(
            package_name,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=chunk,
            continuation_token=continuation_token,
        )
        if not batch:
            break

        collected.extend(batch)
        if continuation_token is None:
            break

    collected = collected[:count]
    return [_serialize_review(bank_code, package_name, payload) for payload in collected]


def scrape_all(banks: Iterable[str], *, lang: str, country: str, count: int) -> List[dict]:
    records: List[dict] = []
    for bank_code in banks:
        package = APP_IDS.get(bank_code)
        if not package:
            print(f'[WARN] Bank "{bank_code}" missing from APP_IDS, skipping.')
            continue
        print(f'Scraping {count} reviews for {bank_code} ({package})...')
        bank_reviews = scrape_bank(bank_code, package, lang=lang, country=country, count=count)
        print(f'  -> Collected {len(bank_reviews)} reviews.')
        records.extend(bank_reviews)
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Scrape Google Play reviews for configured banks.')
    parser.add_argument('--bank', choices=APP_IDS.keys(), action='append', help='Optional bank code to scrape. Provide multiple --bank flags to target a subset. Defaults to all banks.')
    parser.add_argument('--out', default=DATA_PATHS['raw_reviews'], help='Output CSV path. Defaults to config.DATA_PATHS["raw_reviews"].')
    parser.add_argument('--count', type=int, default=SCRAPING_CONFIG['reviews_per_bank'], help='Reviews per bank to fetch (default from config).')
    parser.add_argument('--lang', default=SCRAPING_CONFIG['lang'], help='Language code (default from config).')
    parser.add_argument('--country', default=SCRAPING_CONFIG['country'], help='Country code (default from config).')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_banks = args.bank or list(APP_IDS.keys())
    records = scrape_all(target_banks, lang=args.lang, country=args.country, count=args.count)

    if not records:
        print('No reviews collected. Nothing to write.')
        return

    out_path = args.out
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    pd.DataFrame.from_records(records).to_csv(out_path, index=False)
    print(f'Wrote {len(records)} reviews to {out_path}')


if __name__ == '__main__':
    main()
