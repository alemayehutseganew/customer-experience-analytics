"""Compute sentiment labels and simple keyword/theme extraction.

Usage:
    python src/sentiment.py --in data/clean_example.csv --out data/annotated_example.csv

This script tries Hugging Face transformers first (if available), else falls back to VADER.
It also extracts top TF-IDF keywords per review for simple theme assistance.
"""
import argparse
import os
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer


def compute_sentiment_hf(texts):
    try:
        from transformers import pipeline
        nlp = pipeline('sentiment-analysis', model='distilbert-base-uncased-finetuned-sst-2-english')
        out = nlp(texts, truncation=True)
        labels = [o['label'] for o in out]
        scores = [float(o.get('score', 0.0)) for o in out]
        return labels, scores
    except Exception:
        return None, None


def compute_sentiment_vader(texts):
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    analyzer = SentimentIntensityAnalyzer()
    labels = []
    scores = []
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


def extract_keywords(texts, top_k=3):
    vect = TfidfVectorizer(max_features=1000, stop_words='english', ngram_range=(1,2))
    X = vect.fit_transform(texts)
    feature_names = vect.get_feature_names_out()
    keywords = []
    for i in range(X.shape[0]):
        row = X.getrow(i).toarray().ravel()
        top_idx = row.argsort()[-top_k:][::-1]
        top_terms = [feature_names[j] for j in top_idx if row[j] > 0]
        keywords.append(', '.join(top_terms))
    return keywords


def annotate(in_path, out_path):
    df = pd.read_csv(in_path)
    texts = df['review'].astype(str).tolist()

    labels, scores = compute_sentiment_hf(texts)
    if labels is None:
        labels, scores = compute_sentiment_vader(texts)

    df['sentiment_label'] = labels
    df['sentiment_score'] = scores
    df['keywords'] = extract_keywords(texts)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f'Wrote annotated file to {out_path} (rows: {len(df)})')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--in', dest='in_path', required=True, help='Input cleaned CSV')
    parser.add_argument('--out', required=True, help='Output annotated CSV')
    args = parser.parse_args()
    annotate(args.in_path, args.out)


if __name__ == '__main__':
    main()
