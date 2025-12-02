"""Scrape Google Play reviews for the banks configured in ``config.py``.

The script can scrape all banks defined in :data:`config.APP_IDS` or a specific bank via
the ``--bank`` CLI argument. Output paths, languages, and review counts default to
values declared inside ``config.py`` so that changes can be centralized in one place.
"""
import argparse
import logging
import os
import time
from collections import Counter
from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Tuple

import pandas as pd
from google_play_scraper import Sort, reviews

from config import APP_IDS, BANK_NAMES, DATA_PATHS, QUALITY_THRESHOLDS, SCRAPING_CONFIG

SOURCE = 'google_play'

logging.basicConfig(level=os.getenv('LOGLEVEL', 'INFO'), format='[%(levelname)s] %(message)s')
LOGGER = logging.getLogger(__name__)


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


def _safe_reviews_call(package_name: str, *, lang: str, country: str, count: int, continuation_token, retries: int) -> Tuple[List[dict], str]:
    attempts = 0
    while True:
        try:
            return reviews(
                package_name,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=count,
                continuation_token=continuation_token,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            attempts += 1
            if attempts > retries:
                raise RuntimeError(f'Failed to fetch reviews for {package_name} after {retries} retries') from exc
            wait = min(2 ** attempts, 60)
            LOGGER.warning('Retry %s/%s for %s after error: %s. Sleeping %ss.', attempts, retries, package_name, exc, wait)
            time.sleep(wait)


def scrape_bank(bank_code: str, package_name: str, *, lang: str, country: str, count: int, retries: int) -> List[dict]:
    """Scrape a single bank/app id and return serialized reviews."""
    collected = []
    continuation_token = None
    chunk = min(200, count)

    while len(collected) < count:
        batch, continuation_token = _safe_reviews_call(
            package_name,
            lang=lang,
            country=country,
            count=chunk,
            continuation_token=continuation_token,
            retries=retries,
        )
        if not batch:
            break

        collected.extend(batch)
        if continuation_token is None:
            break

    collected = collected[:count]
    return [_serialize_review(bank_code, package_name, payload) for payload in collected]


def scrape_all(banks: Iterable[str], *, lang: str, country: str, count: int, retries: int) -> List[dict]:
    records: List[dict] = []
    for bank_code in banks:
        package = APP_IDS.get(bank_code)
        if not package:
            LOGGER.warning('Bank "%s" missing from APP_IDS, skipping.', bank_code)
            continue
        LOGGER.info('Scraping %s reviews for %s (%s)...', count, bank_code, package)
        bank_reviews = scrape_bank(bank_code, package, lang=lang, country=country, count=count, retries=retries)
        LOGGER.info('Collected %s reviews for %s.', len(bank_reviews), bank_code)
        records.extend(bank_reviews)
    return records


def enforce_bank_counts(records: Sequence[dict], target_banks: Sequence[str], *, minimum: int, expected: int, minimum_total: Optional[int] = None) -> None:
    counts = Counter(r['bank_code'] for r in records)
    shortfalls = {code: minimum - counts.get(code, 0) for code in target_banks if counts.get(code, 0) < minimum}
    LOGGER.info('Per-bank counts: %s', {code: counts.get(code, 0) for code in target_banks})
    warnings = {code: expected - counts.get(code, 0) for code in target_banks if counts.get(code, 0) < expected}
    if warnings:
        LOGGER.warning('Banks below requested target but above minimum: %s', warnings)
    if shortfalls:
        raise RuntimeError(f'Not enough reviews per bank: {shortfalls}. Re-run scraping or lower the target.')

    if minimum_total is not None:
        total_reviews = len(records)
        if total_reviews < minimum_total:
            raise RuntimeError(
                f'Collected {total_reviews} reviews but require at least {minimum_total} for this run. '
                'Increase --count or update QUALITY_THRESHOLDS.'
            )
        LOGGER.info('Total reviews collected: %s (minimum required %s).', total_reviews, minimum_total)


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
    records = scrape_all(target_banks, lang=args.lang, country=args.country, count=args.count, retries=SCRAPING_CONFIG['max_retries'])

    if not records:
        LOGGER.error('No reviews collected. Nothing to write.')
        return

    minimum_total = QUALITY_THRESHOLDS['min_reviews_per_bank'] * len(target_banks)
    if len(target_banks) == len(APP_IDS):
        minimum_total = max(minimum_total, QUALITY_THRESHOLDS['min_total_reviews'])

    enforce_bank_counts(
        records,
        target_banks,
        minimum=QUALITY_THRESHOLDS['min_reviews_per_bank'],
        expected=args.count,
        minimum_total=minimum_total,
    )
    out_path = args.out
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    pd.DataFrame.from_records(records).to_csv(out_path, index=False)
    LOGGER.info('Wrote %s reviews to %s', len(records), out_path)


if __name__ == '__main__':
    main()
