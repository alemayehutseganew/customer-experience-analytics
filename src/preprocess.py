"""Data cleaning helpers driven by paths declared in ``config.DATA_PATHS``."""

import argparse
import logging
import os
from typing import Dict, List, Optional

import pandas as pd
from langdetect import DetectorFactory, LangDetectException, detect

from config import BANK_NAMES, DATA_PATHS, QUALITY_THRESHOLDS


logging.basicConfig(level=os.getenv('LOGLEVEL', 'INFO'), format='[%(levelname)s] %(message)s')
LOGGER = logging.getLogger(__name__)


DetectorFactory.seed = 0  # make detections deterministic for tests


REQUIRED_COLS: List[str] = ['review', 'rating', 'review_date', 'bank', 'source']
OPTIONAL_COLS: List[str] = ['bank_code', 'package']
DATE_CANDIDATES: List[str] = ['review_date', 'date', 'at', 'created_at', 'created', 'timestamp']


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
    ascii_letters = sum(1 for ch in sample if ord(ch) < 128)
    if ascii_letters / len(sample) < 0.65:
        return False
    try:
        return detect(text) == 'en'
    except LangDetectException:
        return False


def _standardize_bank_label(value: object) -> str:
    normalized = str(value or '').strip()
    if not normalized:
        return normalized
    lower = normalized.lower()
    for code, full_name in BANK_NAMES.items():
        if lower in {code.lower(), full_name.lower()}:
            return full_name
    return normalized


def _log_quality_stats(df: pd.DataFrame, *, label: str, columns: Optional[List[str]] = None) -> None:
    columns = columns or REQUIRED_COLS
    available = [col for col in columns if col in df.columns]
    if not available:
        LOGGER.warning('%s | no overlapping columns to profile (requested=%s).', label, columns)
        return

    null_ratios: Dict[str, float] = df[available].isna().mean().to_dict()
    LOGGER.info('%s | missing ratios: %s', label, {k: round(v, 4) for k, v in null_ratios.items()})
    if 'bank' in df.columns:
        LOGGER.info('%s | bank counts: %s', label, df['bank'].value_counts().to_dict())


def _normalize_review_dates(df: pd.DataFrame) -> pd.Series:
    for candidate in DATE_CANDIDATES:
        if candidate in df.columns:
            normalized = pd.to_datetime(df[candidate], errors='coerce', utc=True)
            if normalized.notna().any():
                normalized = normalized.dt.tz_convert('UTC').dt.tz_localize(None)
                return normalized.dt.normalize()
    return pd.Series(pd.NaT, index=df.index, dtype='datetime64[ns]')


def _validate_missing_ratios(df: pd.DataFrame, columns: List[str], *, label: str) -> None:
    available = [col for col in columns if col in df.columns]
    if not available:
        LOGGER.warning('%s | skipping missing-rate validation because columns are absent: %s', label, columns)
        return

    ratios = df[available].isna().mean()
    offenders = {col: float(ratio) for col, ratio in ratios.items() if ratio > QUALITY_THRESHOLDS['max_missing_ratio']}
    if offenders:
        raise ValueError(
            f'{label} exceeds missing threshold ({QUALITY_THRESHOLDS["max_missing_ratio"]:.2%}): {offenders}'
        )
    LOGGER.info('%s | missing ratios within threshold: %s', label, {c: round(r, 4) for c, r in ratios.items()})


def _validate_volume(df: pd.DataFrame, *, label: str) -> None:
    if 'bank' not in df.columns:
        LOGGER.warning('%s | bank column missing; skipping volume validation.', label)
        return

    counts = df['bank'].value_counts()
    missing_banks = set(BANK_NAMES.values()) - set(counts.index)
    if missing_banks:
        raise ValueError(f'{label} is missing required banks: {missing_banks}')

    shortfalls = {
        bank: QUALITY_THRESHOLDS['min_reviews_per_bank'] - counts.get(bank, 0)
        for bank in BANK_NAMES.values()
        if counts.get(bank, 0) < QUALITY_THRESHOLDS['min_reviews_per_bank']
    }
    if shortfalls:
        raise ValueError(f'{label} below min reviews per bank: {shortfalls}')

    total_reviews = int(counts.sum())
    if total_reviews < QUALITY_THRESHOLDS['min_total_reviews']:
        raise ValueError(
            f'{label} must contain at least {QUALITY_THRESHOLDS["min_total_reviews"]} rows; found {total_reviews}.'
        )

    LOGGER.info('%s | volume OK (total=%s, per-bank=%s)', label, total_reviews, counts.to_dict())


def _enforce_drop_ratio(raw_rows: int, cleaned_rows: int) -> None:
    if raw_rows == 0:
        return

    drop_ratio = 1 - (cleaned_rows / raw_rows)
    if drop_ratio > QUALITY_THRESHOLDS['max_drop_ratio']:
        raise ValueError(
            f'Cleaning removed {drop_ratio:.2%} of rows, exceeding limit '
            f'{QUALITY_THRESHOLDS["max_drop_ratio"]:.2%}. Review preprocessing filters.'
        )
    LOGGER.info('Row retention: %.2f%% (dropped %.2f%%)', 100 * (1 - drop_ratio), 100 * drop_ratio)


def preprocess(in_path: str, out_path: str, final_out_path: Optional[str] = None) -> None:
    if not os.path.exists(in_path):
        raise FileNotFoundError(f'Input file not found: {in_path}')

    df = pd.read_csv(in_path)
    raw_rows = len(df)
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

    if 'bank' not in df.columns:
        for candidate in ['bank_name', 'bank_code']:
            if candidate in df.columns:
                df['bank'] = df[candidate]
                break
    if 'bank' not in df.columns:
        df['bank'] = 'Unknown'
    df['bank'] = df['bank'].apply(_standardize_bank_label)

    df['review_date'] = _normalize_review_dates(df)
    df['rating'] = pd.to_numeric(df.get('rating'), errors='coerce')

    _log_quality_stats(df, label='Pre-drop snapshot', columns=['review', 'rating', 'review_date'])
    _validate_volume(df, label='Raw collection volume')

    if 'source' not in df.columns:
        df['source'] = 'google_play'
    else:
        df['source'] = df['source'].fillna('google_play')

    df = df.dropna(subset=['review_date', 'rating'])
    df['review_date'] = df['review_date'].dt.strftime('%Y-%m-%d')

    out_columns = [c for c in REQUIRED_COLS if c in df.columns]
    out_columns += [c for c in OPTIONAL_COLS if c in df.columns]
    missing_required = set(REQUIRED_COLS) - set(out_columns)
    if missing_required:
        raise ValueError(f'Missing required columns after cleaning: {missing_required}')

    out_df = df[out_columns].copy()
    cleaned_rows = len(out_df)
    LOGGER.info('Cleaned dataset rows: %s (dropped %s)', cleaned_rows, raw_rows - cleaned_rows)
    _enforce_drop_ratio(raw_rows, cleaned_rows)
    _validate_missing_ratios(out_df, REQUIRED_COLS, label='Post-clean missing-rate validation')
    _validate_volume(out_df, label='Post-clean volume check')
    _log_quality_stats(out_df, label='Post-clean summary')

    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    out_df.to_csv(out_path, index=False)
    LOGGER.info('Wrote cleaned data to %s (rows: %s)', out_path, cleaned_rows)

    if final_out_path:
        final_out_path = final_out_path.strip()
        if final_out_path and final_out_path != out_path:
            os.makedirs(os.path.dirname(final_out_path) or '.', exist_ok=True)
            out_df.to_csv(final_out_path, index=False)
            LOGGER.info('Synced single consolidated CSV to %s', final_out_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Clean raw reviews dataset.')
    parser.add_argument('--in', dest='in_path', default=DATA_PATHS['raw_reviews'], help='Input CSV path (defaults to config.DATA_PATHS["raw_reviews"])')
    parser.add_argument('--out', dest='out_path', default=DATA_PATHS['processed_reviews'], help='Output CSV path (defaults to config.DATA_PATHS["processed_reviews"])')
    parser.add_argument('--final', dest='final_out_path', default=DATA_PATHS.get('final_results'), help='Optional consolidated CSV target (defaults to config.DATA_PATHS["final_results"]. Provide blank to skip).')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    final_out_path = args.final_out_path if args.final_out_path else None
    preprocess(args.in_path, args.out_path, final_out_path=final_out_path)


if __name__ == '__main__':
    main()
