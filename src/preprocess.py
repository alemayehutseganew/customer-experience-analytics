"""Data cleaning helpers driven by paths declared in ``config.DATA_PATHS``."""

import argparse
import os
from typing import List

import pandas as pd
from langdetect import DetectorFactory, LangDetectException, detect

from config import DATA_PATHS


DetectorFactory.seed = 0  # make detections deterministic for tests


REQUIRED_COLS: List[str] = ['review', 'rating', 'review_date', 'bank', 'source']
OPTIONAL_COLS: List[str] = ['bank_code', 'package']


def is_english(text: str) -> bool:
    """Return True when langdetect classifies the text as English."""
    text = str(text or '').strip()
    if not text:
        return False
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    if ascii_chars / max(len(text), 1) >= 0.85:
        return True
    sample = ''.join(ch for ch in text if ch.isalpha())
    if len(sample) < 3:  # skip extremely short/non letter strings
        return False
    try:
        return detect(text) == 'en'
    except LangDetectException:
        return False


def preprocess(in_path: str, out_path: str) -> None:
    if not os.path.exists(in_path):
        raise FileNotFoundError(f'Input file not found: {in_path}')

    df = pd.read_csv(in_path)
    df.columns = [c.strip().lower() for c in df.columns]

    if 'review' not in df.columns:
        for candidate in ['content', 'text', 'body']:
            if candidate in df.columns:
                df = df.rename(columns={candidate: 'review'})
                break
    if 'review' not in df.columns:
        raise ValueError('Input data must contain a review/content column')

    df['review'] = df['review'].fillna('').astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
    df = df[df['review'] != '']
    df = df[df['review'].apply(is_english)]
    df = df.drop_duplicates(subset=['review'])

    if 'review_date' in df.columns:
        df['review_date'] = pd.to_datetime(df['review_date'], errors='coerce').dt.date
    else:
        df['review_date'] = pd.to_datetime(df.get('date'), errors='coerce').dt.date

    df['rating'] = pd.to_numeric(df.get('rating'), errors='coerce')

    if 'bank' not in df.columns:
        for candidate in ['bank_name', 'bank_code']:
            if candidate in df.columns:
                df['bank'] = df[candidate]
                break
    if 'bank' not in df.columns:
        df['bank'] = 'Unknown'

    if 'source' not in df.columns:
        df['source'] = 'google_play'
    else:
        df['source'] = df['source'].fillna('google_play')

    out_columns = [c for c in REQUIRED_COLS if c in df.columns]
    out_columns += [c for c in OPTIONAL_COLS if c in df.columns]
    out_df = df[out_columns].copy()
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    out_df.to_csv(out_path, index=False)
    print(f'Wrote cleaned data to {out_path} (rows: {len(out_df)})')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Clean raw reviews dataset.')
    parser.add_argument('--in', dest='in_path', default=DATA_PATHS['raw_reviews'], help='Input CSV path (defaults to config.DATA_PATHS["raw_reviews"])')
    parser.add_argument('--out', dest='out_path', default=DATA_PATHS['processed_reviews'], help='Output CSV path (defaults to config.DATA_PATHS["processed_reviews"])')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    preprocess(args.in_path, args.out_path)


if __name__ == '__main__':
    main()
