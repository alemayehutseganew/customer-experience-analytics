"""Add sentiment labels/keywords to the cleaned dataset using config defaults."""

import argparse
import logging
import os
from typing import List, Sequence, Tuple

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
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


def perform_topic_modeling(texts: Sequence[str], n_topics: int = 5) -> Tuple[List[str], pd.DataFrame]:
    """
    Perform LDA topic modeling on the texts.
    Returns:
        - List of dominant topic index for each text
        - DataFrame of topics and their top words
    """
    if not texts:
        return [], pd.DataFrame()

    # Use CountVectorizer for LDA
    tf_vectorizer = CountVectorizer(max_df=0.95, min_df=2, stop_words='english')
    tf = tf_vectorizer.fit_transform(texts)
    
    lda = LatentDirichletAllocation(n_components=n_topics, max_iter=10, learning_method='online', random_state=0)
    lda.fit(tf)
    
    # Get dominant topic for each document
    topic_results = lda.transform(tf)
    dominant_topics = topic_results.argmax(axis=1)
    
    # Extract top words for each topic
    feature_names = tf_vectorizer.get_feature_names_out()
    topics_data = []
    for topic_idx, topic in enumerate(lda.components_):
        top_features_ind = topic.argsort()[:-11:-1]
        top_words = [feature_names[i] for i in top_features_ind]
        topics_data.append({'Topic': topic_idx, 'Top Words': ", ".join(top_words)})
        
    return [int(t) for t in dominant_topics], pd.DataFrame(topics_data)


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

    labels = scores = None
    if use_hf:
        labels, scores = compute_sentiment_hf(texts)
    if labels is None:
        labels, scores = compute_sentiment_vader(texts)

    df['sentiment_label'] = labels
    df['sentiment_score'] = scores
    df['keywords'] = extract_keywords(texts, top_k=top_k)
    
    # Add Topic Modeling
    LOGGER.info("Performing Topic Modeling...")
    dominant_topics, topics_df = perform_topic_modeling(texts, n_topics=5)
    df['topic_id'] = dominant_topics
    
    # Save topics summary
    topics_summary_path = os.path.join(os.path.dirname(out_path), 'topics_summary.csv')
    topics_df.to_csv(topics_summary_path, index=False)
    LOGGER.info(f"Wrote topics summary to {topics_summary_path}")

    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    df.to_csv(out_path, index=False)
    LOGGER.info('Wrote annotated file to %s (rows: %s)', out_path, len(df))


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




