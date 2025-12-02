"""Create Postgres schema and insert cleaned/annotated reviews."""

import argparse
import logging
import os
from typing import Optional

import pandas as pd
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, MetaData, String, Table, Text, create_engine

from config import APP_IDS, BANK_NAMES, DATA_PATHS, DB_URL


REQUIRED_INPUT_COLS = {'bank', 'review', 'rating', 'review_date', 'source'}

logging.basicConfig(level=os.getenv('LOGLEVEL', 'INFO'), format='[%(levelname)s] %(message)s')
LOGGER = logging.getLogger(__name__)


def create_schema(engine):
    meta = MetaData()
    banks = Table(
        'banks', meta,
        Column('bank_id', Integer, primary_key=True, autoincrement=True),
        Column('bank_name', String, nullable=False),
        Column('app_name', String),
    )

    reviews = Table(
        'reviews', meta,
        Column('review_id', Integer, primary_key=True, autoincrement=True),
        Column('bank_id', Integer, ForeignKey('banks.bank_id')),
        Column('review_text', Text),
        Column('rating', Integer),
        Column('review_date', Date),
        Column('sentiment_label', String),
        Column('sentiment_score', Float),
        Column('source', String),
    )
    meta.create_all(engine)
    print('Created tables (if not existing)')
    return banks, reviews


def _bank_code_from_row(row: pd.Series) -> Optional[str]:
    if 'bank_code' in row and isinstance(row['bank_code'], str):
        return row['bank_code']
    name_to_code = {v: k for k, v in BANK_NAMES.items()}
    bank_name = row.get('bank')
    if isinstance(bank_name, str):
        return name_to_code.get(bank_name)
    return None


def insert_reviews(engine, df):
    missing_cols = REQUIRED_INPUT_COLS - set(df.columns)
    if missing_cols:
        raise ValueError(f'Input data is missing required columns: {missing_cols}')

    null_ratios = df[list(REQUIRED_INPUT_COLS)].isna().mean()
    if null_ratios.any():
        raise ValueError(f'Nulls detected in required columns: {null_ratios.to_dict()}')

    meta = MetaData()
    meta.reflect(bind=engine)
    banks = meta.tables.get('banks')
    reviews = meta.tables.get('reviews')

    with engine.begin() as conn:
        bank_map = {}
        for bank_name in df['bank'].dropna().unique():
            res = conn.execute(banks.select().where(banks.c.bank_name == bank_name)).fetchone()
            if res:
                bank_map[bank_name] = res._mapping['bank_id']
            else:
                sample_row = df[df['bank'] == bank_name].iloc[0]
                bank_code = _bank_code_from_row(sample_row)
                package = APP_IDS.get(bank_code) if bank_code else None
                inserted = conn.execute(banks.insert().values(bank_name=bank_name, app_name=package))
                bank_map[bank_name] = inserted.inserted_primary_key[0]

        ins = []
        for _, row in df.iterrows():
            bid = bank_map.get(row.get('bank'))
            ins.append({
                'bank_id': bid,
                'review_text': row.get('review'),
                'rating': int(row.get('rating')) if pd.notna(row.get('rating')) else None,
                'review_date': row.get('review_date') if 'review_date' in row else None,
                'sentiment_label': row.get('sentiment_label') if 'sentiment_label' in row else None,
                'sentiment_score': float(row.get('sentiment_score')) if 'sentiment_score' in row and pd.notna(row.get('sentiment_score')) else None,
                'source': row.get('source'),
            })
        conn.execute(reviews.insert(), ins)
    LOGGER.info('Inserted %s reviews into Postgres', len(ins))


def main():
    parser = argparse.ArgumentParser(description='Load sentiment-enriched reviews into Postgres.')
    parser.add_argument('--in', dest='in_path', default=DATA_PATHS['sentiment_results'], help='Input annotated CSV path (defaults to config).')
    parser.add_argument('--dburl', default=DB_URL, help='Postgres DB URL (or set PGURL env).')
    args = parser.parse_args()

    df = pd.read_csv(args.in_path, parse_dates=['review_date'])
    LOGGER.info('Loaded %s annotated rows from %s', len(df), args.in_path)
    engine = create_engine(args.dburl)
    create_schema(engine)
    insert_reviews(engine, df)


if __name__ == '__main__':
    main()
