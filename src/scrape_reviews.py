"""Scrape Google Play reviews for a given app package name.

Usage example:
    python src/scrape_reviews.py --package com.example.app --bank "Example Bank" --count 500 --out data/raw_example.csv

Notes:
- Uses the `google_play_scraper` Python package (https://pypi.org/project/google-play-scraper/).
"""
import argparse
import csv
import os
from google_play_scraper import reviews, Sort


def scrape(package_name, lang='en', country='us', count=500):
    # google_play_scraper.reviews returns a tuple (results, continuation_token)
    # We request in chunks of 200 until we reach `count` or no more results.
    collected = []
    continuation_token = None
    remaining = count
    chunk = 200
    while remaining > 0:
        n = min(chunk, remaining)
        result, continuation_token = reviews(
            package_name,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=n,
            continuation_token=continuation_token,
        )
        if not result:
            break
        collected.extend(result)
        remaining = count - len(collected)
        if continuation_token is None:
            break
    return collected


def to_csv(items, bank_name, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['review', 'rating', 'date', 'bank', 'source'])
        for it in items:
            review = it.get('content') or it.get('review') or ''
            rating = it.get('score') or it.get('rating') or ''
            date = it.get('at') or it.get('date') or ''
            writer.writerow([review, rating, date, bank_name, 'google_play'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True, help='App package name (e.g., com.bank.app)')
    parser.add_argument('--bank', required=True, help='Bank name (e.g., CBE)')
    parser.add_argument('--count', type=int, default=500, help='Number of reviews to fetch')
    parser.add_argument('--out', required=True, help='Output CSV path')
    parser.add_argument('--lang', default='en', help='Language code (default: en)')
    parser.add_argument('--country', default='us', help='Country code (default: us)')
    args = parser.parse_args()

    items = scrape(args.package, lang=args.lang, country=args.country, count=args.count)
    print(f'Scraped {len(items)} reviews for {args.package}')
    to_csv(items, args.bank, args.out)
    print(f'Wrote CSV to {args.out}')


if __name__ == '__main__':
    main()
