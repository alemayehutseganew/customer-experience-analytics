"""Preprocess raw CSV of reviews.
 - Remove duplicates
 - Normalize dates to YYYY-MM-DD
 - Drop rows with empty reviews
"""
import argparse
import os
import pandas as pd


def preprocess(in_path, out_path):
    df = pd.read_csv(in_path)
    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]
    # Expect at least: review, rating, date, bank, source
    if 'review' not in df.columns:
        # try common alternatives
        if 'content' in df.columns:
            df = df.rename(columns={'content': 'review'})
    # Drop empty reviews
    df = df[df['review'].notna()]
    df = df[df['review'].str.strip() != '']
    # Remove duplicates on review text
    df = df.drop_duplicates(subset=['review'])
    # Normalize date
    if 'date' in df.columns:
        df['review_date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
    else:
        df['review_date'] = pd.NaT
    # Ensure rating is numeric
    if 'rating' in df.columns:
        df['rating'] = pd.to_numeric(df['rating'], errors='coerce').astype('Int64')

    # Keep only useful columns
    keep = [c for c in ['review', 'rating', 'review_date', 'bank', 'source'] if c in df.columns]
    out_df = df[keep].copy()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out_df.to_csv(out_path, index=False)
    print(f'Wrote cleaned data to {out_path} (rows: {len(out_df)})')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--in', dest='in_path', required=True, help='Input raw CSV path')
    parser.add_argument('--out', required=True, help='Output cleaned CSV path')
    args = parser.parse_args()
    preprocess(args.in_path, args.out)


if __name__ == '__main__':
    main()
