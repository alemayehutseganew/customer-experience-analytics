"""Create Postgres schema and insert cleaned/annotated reviews.

Usage (example):
  set PGURL=postgresql://user:password@localhost:5432/bank_reviews; python src/db.py --in data/annotated_example.csv

Edit the `DATABASE_URL` default or pass via `PGURL` env var.
"""
import argparse
import os
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Date, Float, Text, ForeignKey


DEFAULT_DBURL = os.environ.get('PGURL') or 'postgresql://postgres:postgres@localhost:5432/bank_reviews'


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


def insert_reviews(engine, df):
    meta = MetaData(bind=engine)
    meta.reflect()
    banks = meta.tables.get('banks')
    reviews = meta.tables.get('reviews')
    conn = engine.connect()
    # Insert distinct banks
    bank_map = {}
    for bank in df['bank'].dropna().unique():
        res = conn.execute(banks.select().where(banks.c.bank_name == bank)).fetchone()
        if res:
            bank_map[bank] = res['bank_id']
        else:
            r = conn.execute(banks.insert().values(bank_name=bank, app_name=None))
            bank_map[bank] = r.inserted_primary_key[0]

    # Insert reviews
    ins = []
    for _, row in df.iterrows():
        bid = bank_map.get(row.get('bank'))
        ins.append({
            'bank_id': bid,
            'review_text': row.get('review'),
            'rating': int(row.get('rating')) if pd.notna(row.get('rating')) else None,
            'review_date': row.get('review_date') if 'review_date' in row else None,
            'sentiment_label': row.get('sentiment_label'),
            'sentiment_score': float(row.get('sentiment_score')) if pd.notna(row.get('sentiment_score')) else None,
            'source': row.get('source'),
        })
    conn.execute(reviews.insert(), ins)
    print(f'Inserted {len(ins)} reviews')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--in', dest='in_path', required=True, help='Input annotated CSV')
    parser.add_argument('--dburl', default=DEFAULT_DBURL, help='Postgres DB URL')
    args = parser.parse_args()
    df = pd.read_csv(args.in_path, parse_dates=['review_date'])
    engine = create_engine(args.dburl)
    create_schema(engine)
    insert_reviews(engine, df)


if __name__ == '__main__':
    main()
