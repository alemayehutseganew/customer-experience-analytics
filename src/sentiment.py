"""Add sentiment labels/keywords to the cleaned dataset using config defaults."""

import argparse
import logging
import os
from typing import Dict, List, Sequence, Tuple

import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation

from config import DATA_PATHS


HF_MODEL = 'distilbert-base-uncased-finetuned-sst-2-english'

logging.basicConfig(level=os.getenv('LOGLEVEL', 'INFO'), format='[%(levelname)s] %(message)s')
LOGGER = logging.getLogger(__name__)


def compute_sentiment_hf(texts: Sequence[str]) -> Tuple[List[str], List[float]]:
    try:
        from transformers import pipeline

        nlp = pipeline('sentiment-analysis', model=HF_MODEL)
        out = nlp(texts, truncation=True)
        labels = [o['label'] for o in out]
        scores = [float(o.get('score', 0.0)) for o in out]
        return labels, scores
    except Exception as exc:  # pragma: no cover - optional dependency
        LOGGER.warning('Falling back to VADER because transformer pipeline failed: %s', exc)
        return None, None


def compute_sentiment_vader(texts: Sequence[str]) -> Tuple[List[str], List[float]]:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    analyzer = SentimentIntensityAnalyzer()
    labels: List[str] = []
    scores: List[float] = []
    for t in texts:
        s = analyzer.polarity_scores(str(t))
        score = s['compound']
        if score >= 0.05:
            lab = 'POSITIVE'
        elif score <= -0.05:
            lab = 'NEGATIVE'
        else:
            lab = 'NEUTRAL'
        labels.append(lab)
        scores.append(score)
    return labels, scores


def extract_keywords(texts: Sequence[str], top_k: int = 3) -> List[str]:
    if not texts:
        return []

    vect = TfidfVectorizer(max_features=1000, stop_words='english', ngram_range=(1, 2))
    X = vect.fit_transform(texts)
    feature_names = vect.get_feature_names_out()
    keywords: List[str] = []
    for i in range(X.shape[0]):
        row = X.getrow(i).toarray().ravel()
        top_idx = row.argsort()[-top_k:][::-1]
        top_terms = [feature_names[j] for j in top_idx if row[j] > 0]
        keywords.append(', '.join(top_terms))
    return keywords


def perform_topic_modeling(texts: Sequence[str], n_topics: int = 5) -> Tuple[List[int], pd.DataFrame]:
    """Return dominant topics and keyword descriptors for a list of reviews."""

    if not texts:
        return [], pd.DataFrame()

    cleaned_texts = [str(t) for t in texts if str(t).strip()]
    if len(cleaned_texts) < 3:
        LOGGER.warning('Not enough non-empty reviews (%s) to model topics.', len(cleaned_texts))
        return [-1] * len(texts), pd.DataFrame()

    min_df = 2 if len(cleaned_texts) >= 20 else 1
    tf_vectorizer = CountVectorizer(max_df=0.95, min_df=min_df, stop_words='english')

    try:
        tf = tf_vectorizer.fit_transform(cleaned_texts)
    except ValueError as exc:  # pragma: no cover - defensive
        LOGGER.warning('Skipping topic modeling because vectorizer failed: %s', exc)
        return [-1] * len(texts), pd.DataFrame()

    n_components = max(1, min(n_topics, tf.shape[0]))
    lda = LatentDirichletAllocation(
        n_components=n_components,
        max_iter=10,
        learning_method='online',
        random_state=0,
    )
    lda.fit(tf)

    topic_results = lda.transform(tf)
    dominant_topics = topic_results.argmax(axis=1)

    feature_names = tf_vectorizer.get_feature_names_out()
    topics_data = []
    for topic_idx, topic in enumerate(lda.components_):
        top_features_ind = topic.argsort()[:-11:-1]
        top_words = [feature_names[i] for i in top_features_ind]
        topics_data.append({'Topic': topic_idx, 'Top Words': ", ".join(top_words)})

    expanded_topics: List[int] = []
    dom_iter = iter(dominant_topics)
    for text in texts:
        expanded_topics.append(int(next(dom_iter)) if str(text).strip() else -1)

    return expanded_topics, pd.DataFrame(topics_data)


def annotate(in_path: str, out_path: str, *, use_hf: bool = True, top_k: int = 3) -> None:
    if not os.path.exists(in_path):
        raise FileNotFoundError(f'Input file not found: {in_path}')

    df = pd.read_csv(in_path)
    if 'review' not in df.columns:
        raise ValueError('Input data must include a "review" column. Did you run preprocess.py?')

    texts = df['review'].astype(str).fillna('').tolist()
    if not texts:
        print('No reviews present in input file; skipping sentiment scoring.')
        return

    needs_sentiment = not ({'sentiment_label', 'sentiment_score'} <= set(df.columns))
    if needs_sentiment:
        labels = scores = None
        if use_hf:
            labels, scores = compute_sentiment_hf(texts)
        if labels is None:
            labels, scores = compute_sentiment_vader(texts)

        df['sentiment_label'] = labels
        df['sentiment_score'] = scores
    else:
        LOGGER.info('Sentiment columns already present; skipping recomputation.')

    df['keywords'] = extract_keywords(texts, top_k=top_k)

    summary_records: List[Dict[str, object]] = []
    df['topic_id'] = -1
    df['topic_label'] = 'insufficient_data'

    if 'bank' not in df.columns:
        LOGGER.warning('Column "bank" missing; skipping per-bank topic modeling.')
    else:
        LOGGER.info('Performing per-bank topic modeling...')
        for bank, bank_df in df.groupby('bank'):
            bank_texts = bank_df['review'].astype(str).tolist()
            valid_count = sum(1 for text in bank_texts if str(text).strip())
            if valid_count < 5:
                LOGGER.info('Skipping bank %s due to <5 valid reviews.', bank)
                continue

            n_topics = min(5, max(1, len(bank_df) // 10)) or 1
            dominant_topics, topics_df = perform_topic_modeling(bank_texts, n_topics=n_topics)
            if not topics_df.empty and dominant_topics:
                idx = bank_df.index
                df.loc[idx, 'topic_id'] = dominant_topics
                topic_lookup = topics_df.set_index('Topic')['Top Words'].to_dict()
                df.loc[idx, 'topic_label'] = [
                    topic_lookup.get(t, 'insufficient_data') if t >= 0 else 'insufficient_data'
                    for t in dominant_topics
                ]

                topic_counts = (
                    pd.Series([t for t in dominant_topics if t >= 0])
                    .value_counts()
                    .sort_values(ascending=False)
                )
                for topic_id, count in topic_counts.items():
                    topic_mask = (df['bank'] == bank) & (df['topic_id'] == topic_id)
                    summary_records.append({
                        'bank': bank,
                        'topic_id': int(topic_id),
                        'topic_keywords': topic_lookup.get(topic_id, ''),
                        'share_of_reviews': round(count / len(bank_df), 3),
                        'avg_sentiment': float(df.loc[topic_mask, 'sentiment_score'].mean()),
                    })
            else:
                LOGGER.info('Topic modeling fell back to defaults for bank %s.', bank)

    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    df.to_csv(out_path, index=False)
    LOGGER.info('Wrote annotated file to %s (rows: %s)', out_path, len(df))

    if summary_records:
        topics_summary_path = os.path.join(os.path.dirname(out_path), 'topics_summary.csv')
        pd.DataFrame(summary_records).to_csv(topics_summary_path, index=False)
        LOGGER.info('Wrote per-bank topics summary to %s', topics_summary_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Attach sentiment labels and keywords to processed reviews.')
    parser.add_argument('--in', dest='in_path', default=DATA_PATHS['processed_reviews'], help='Input CSV (default: processed reviews from config).')
    parser.add_argument('--out', dest='out_path', default=DATA_PATHS['sentiment_results'], help='Output CSV (default: sentiment path from config).')
    parser.add_argument('--top-k', dest='top_k', type=int, default=3, help='Number of keywords per review (default: 3).')
    parser.add_argument('--disable-hf', action='store_true', help='Force using VADER only (skip Hugging Face pipeline).')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    annotate(args.in_path, args.out_path, use_hf=not args.disable_hf, top_k=args.top_k)


if __name__ == '__main__':
    main()




