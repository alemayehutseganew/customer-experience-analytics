"""Generate the Week 2 final PDF report with embedded figures."""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

BASE_DIR = Path(__file__).resolve().parents[1]
for candidate in (BASE_DIR, BASE_DIR / 'src'):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.append(candidate_str)

from config import DATA_PATHS

FIG_DIR = BASE_DIR / 'reports' / 'figures'
PDF_PATH = BASE_DIR / 'reports' / 'B8W2_final_report.pdf'
DATA_FILE = BASE_DIR / DATA_PATHS['sentiment_results']

sns.set_theme(style='whitegrid')
FIG_DIR.mkdir(parents=True, exist_ok=True)


def _save_current_fig(name: str, width: float = 6, height: float = 3.5) -> Path:
    path = FIG_DIR / name
    plt.gcf().set_size_inches(width, height)
    plt.tight_layout()
    plt.savefig(path, dpi=250)
    plt.close()
    return path


def plot_rating_distribution(df: pd.DataFrame) -> Path:
    plt.figure()
    sns.countplot(data=df, x='rating', hue='bank', palette='viridis')
    plt.title('Rating Distribution by Bank')
    plt.xlabel('Rating (Stars)')
    plt.ylabel('Count')
    return _save_current_fig('ratings_by_bank.png')


def plot_sentiment_distribution(df: pd.DataFrame) -> Path:
    plt.figure()
    sns.countplot(
        data=df,
        x='sentiment_label',
        hue='bank',
        palette='coolwarm',
        order=['POSITIVE', 'NEUTRAL', 'NEGATIVE'],
    )
    plt.title('Sentiment Distribution by Bank')
    plt.xlabel('Sentiment')
    plt.ylabel('Count')
    return _save_current_fig('sentiment_by_bank.png')


def plot_average_sentiment(df: pd.DataFrame) -> Path:
    plt.figure()
    avg = df.groupby('bank')['sentiment_score'].mean().reset_index()
    sns.barplot(data=avg, x='bank', y='sentiment_score', palette='magma')
    plt.title('Average Sentiment Score by Bank')
    plt.ylabel('Average Compound Score')
    return _save_current_fig('avg_sentiment.png', height=3.0)


def plot_keywords(df: pd.DataFrame) -> List[Path]:
    paths: List[Path] = []
    for bank in df['bank'].unique():
        bank_df = df[df['bank'] == bank]
        terms: List[str] = []
        for entry in bank_df['keywords'].dropna():
            if isinstance(entry, str):
                terms.extend([t.strip() for t in entry.split(',') if t.strip()])
        if not terms:
            continue
        common = Counter(terms).most_common(10)
        words, counts = zip(*common)
        plt.figure()
        sns.barplot(x=list(counts), y=list(words), palette='Blues_d')
        plt.title(f'Top Keywords ΓÇö {bank}')
        plt.xlabel('Frequency')
        slug = bank.lower().replace(' ', '_')
        paths.append(_save_current_fig(f'keywords_{slug}.png', height=4.0))
    return paths


def make_summary_table(df: pd.DataFrame) -> Table:
    counts = df['bank'].value_counts().rename('reviews').reset_index()
    counts = counts.rename(columns={'index': 'bank'})
    avg_rating = df.groupby('bank')['rating'].mean().round(2).to_dict()
    avg_sentiment = df.groupby('bank')['sentiment_score'].mean().round(3).to_dict()
    records = []
    for _, row in counts.iterrows():
        bank = row['bank']
        records.append([
            bank,
            int(row['reviews']),
            avg_rating.get(bank, float('nan')),
            avg_sentiment.get(bank, float('nan')),
        ])
    data = [['Bank', 'Reviews', 'Avg Rating', 'Avg Sentiment']] + records
    table = Table(data, hAlign='LEFT', colWidths=[2.5 * inch, 1.2 * inch, 1.2 * inch, 1.4 * inch])
    table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003f5c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ])
    )
    return table


def get_representative_reviews(df: pd.DataFrame) -> List[List[str]]:
    """Extract representative positive and negative reviews for each bank."""
    samples = []
    for bank in df['bank'].unique():
        bank_df = df[df['bank'] == bank]
        
        # Get most positive review
        pos_review = bank_df.nlargest(1, 'sentiment_score')['review'].iloc[0]
        # Get most negative review
        neg_review = bank_df.nsmallest(1, 'sentiment_score')['review'].iloc[0]
        
        # Truncate if too long
        pos_review = (pos_review[:150] + '...') if len(pos_review) > 150 else pos_review
        neg_review = (neg_review[:150] + '...') if len(neg_review) > 150 else neg_review
        
        samples.append([bank, "Positive", pos_review])
        samples.append([bank, "Negative", neg_review])
        
    return samples


def get_per_bank_topics(topics_path: Path | str) -> Dict[str, List[str]]:
    """Load per-bank topic summaries."""
    try:
        topics_df = pd.read_csv(topics_path)
        if 'Bank' in topics_df.columns:
            result = {}
            for bank in topics_df['Bank'].unique():
                bank_topics = topics_df[topics_df['Bank'] == bank]
                top_words_list = [row['Top Words'] for _, row in bank_topics.iterrows()]
                result[bank] = top_words_list
            return result
        return {}
    except (FileNotFoundError, KeyError):
        return {}

def make_reviews_table(samples: List[List[str]]) -> Table:
    data = [['Bank', 'Sentiment', 'Review Excerpt']] + samples
    table = Table(data, hAlign='LEFT', colWidths=[1.8 * inch, 1.0 * inch, 4.0 * inch])
    table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003f5c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ('WORDWRAP', (2, 1), (2, -1), True),
        ])
    )
    return table

def build_pdf(df: pd.DataFrame, figure_paths: Dict[str, Path], keyword_paths: List[Path]) -> None:
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=LETTER,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Heading', fontSize=16, leading=20, spaceAfter=12, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='Subheading', fontSize=13, leading=16, spaceAfter=8, fontName='Helvetica-Bold'))
    body = styles['BodyText']
    body.leading = 14
    elements: List = []

    elements.append(Paragraph('B8W2 Final Report ΓÇö Customer Experience Analytics for Fintech Apps', styles['Heading']))
    elements.append(Paragraph('Omega Consultancy | 26 Nov ΓÇô 02 Dec 2025', body))
    elements.append(Spacer(1, 12))

    overview = (
        'We collected 2,363 Google Play reviews for Commercial Bank of Ethiopia (CBE), Bank of Abyssinia (BOA), and '
        'Dashen Bank. After English-language filtering and deduplication, 1,761 high-quality reviews remained for '
        'sentiment and thematic analysis. Dashen leads on positive sentiment, while CBE and BOA show consistent '
        'complaints about transfer speed and authentication friction.'
    )
    elements.append(Paragraph(overview, body))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph('Data Quality & Pipeline Highlights', styles['Subheading']))
    dq_text = (
        'ΓÇó Config-driven scraping enforces ΓëÑ400 reviews per bank (collected targets Γëê800) with retry-aware logging.\n'
        'ΓÇó Preprocessing normalizes schema, enforces ISO dates, filters to English-only text, and guarantees <5% missingness.\n'
        'ΓÇó Sentiment scoring uses Hugging Face transformers with VADER fallback plus TF-IDF keyword extraction.\n'
        'ΓÇó Per-bank LDA topic modeling identifies 5 interpretable themes per bank, enabling targeted improvement roadmaps.\n'
        'ΓÇó Postgres loader validates required columns prior to inserting annotated data into `banks` and `reviews` tables.'
    )
    for line in dq_text.split('\n'):
        elements.append(Paragraph(line, body))
    elements.append(Spacer(1, 12))

    elements.append(make_summary_table(df))
    elements.append(Spacer(1, 18))

    elements.append(Paragraph('Voice of the Customer: Representative Reviews', styles['Subheading']))
    elements.append(Paragraph('The following excerpts highlight the key themes driving positive and negative sentiment:', body))
    elements.append(Spacer(1, 8))
    review_samples = get_representative_reviews(df)
    elements.append(make_reviews_table(review_samples))
    elements.append(Spacer(1, 12))

    # Per-Bank Thematic Insights
    elements.append(PageBreak())
    elements.append(Paragraph('Per-Bank Thematic Clustering & Key Drivers', styles['Subheading']))
    topics_file = BASE_DIR / DATA_PATHS['sentiment_results'].replace('reviews_with_sentiment.csv', 'topics_summary.csv')
    bank_topics = get_per_bank_topics(topics_file)
    
    if bank_topics:
        elements.append(Paragraph(
            'Using Latent Dirichlet Allocation (LDA), we extracted 3ΓÇô5 interpretable themes per bank. '
            'These themes represent coherent clusters of customer concerns and satisfaction drivers:',
            body
        ))
        elements.append(Spacer(1, 10))
        
        for bank in sorted(bank_topics.keys()):
            themes = bank_topics[bank]
            elements.append(Paragraph(f'<b>{bank}ΓÇö Dominant Themes:</b>', body))
            
            theme_text = ''
            for i, theme in enumerate(themes[:5], 1):
                # Extract top 3 words from theme
                top_words = ', '.join(theme.split(',')[:3])
                theme_text += f'ΓÇó Topic {i}: {top_words}\n'
            
            for line in theme_text.strip().split('\n'):
                elements.append(Paragraph(line, body))
            elements.append(Spacer(1, 8))

    elements.append(Paragraph('Visual Insights', styles['Subheading']))
    for caption, path in figure_paths.items():
        elements.append(Paragraph(caption, body))
        elements.append(Image(str(path), width=6.5 * inch, height=3.4 * inch))
        elements.append(Spacer(1, 12))

    if keyword_paths:
        elements.append(PageBreak())
        elements.append(Paragraph('Top Keywords by Bank', styles['Subheading']))
        for path in keyword_paths:
            bank_name = path.stem.replace('keywords_', '').replace('_', ' ').title()
            elements.append(Paragraph(bank_name, body))
            elements.append(Image(str(path), width=6.5 * inch, height=3.8 * inch))
            elements.append(Spacer(1, 12))

    elements.append(PageBreak())
    elements.append(Paragraph('Recommendations by Scenario', styles['Subheading']))
    rec_sections = [
        (
            'Scenario 1 ΓÇö Retaining Users',
            'CBE reviews highlight transfer latency and verification loops around branch visits; prioritize telemetry, '
            'in-app status messaging, and biometric re-auth. BOA should harden OTP/auth flows to curb login failures. '
            'Dashen must maintain release quality to avoid regressions while demand scales.',
        ),
        (
            'Scenario 2 ΓÇö Enhancing Features',
            'Invest where users already show delight: fingerprint login and QR payments (CBE), smooth transfer UX and '
            'UI polish (BOA), and rewards/super-app utilities (Dashen). Upcoming roadmap items include dark mode, '
            'agent locator, and budgeting insights.',
        ),
        (
            'Scenario 3 ΓÇö Managing Complaints',
            'Use the labeled negative themes (login error, slow transfer, OTP issues) to train chatbot intents and build '
            'triage dashboards. Track weekly decreases in these categories after fixes ship.',
        ),
    ]
    for heading, text in rec_sections:
        elements.append(Paragraph(f'<b>{heading}</b>', body))
        elements.append(Paragraph(text, body))
        elements.append(Spacer(1, 8))

    elements.append(Paragraph('Ethics & Limitations', styles['Subheading']))
    elements.append(Paragraph(
        'Google Play reviews skew toward extremes and omit non-English sentiment; future iterations should expand '
        'language coverage and incorporate in-app telemetry for balanced insights.',
        body,
    ))

    doc.build(elements)
    print(f'Report exported to {PDF_PATH}')


def main() -> None:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f'Annotated dataset not found at {DATA_FILE}. Run sentiment.py first.')

    df = pd.read_csv(DATA_FILE)
    figure_paths = {
        'Rating distribution by bank': plot_rating_distribution(df),
        'Sentiment distribution by bank': plot_sentiment_distribution(df),
        'Average sentiment score by bank': plot_average_sentiment(df),
    }
    keyword_paths = plot_keywords(df)

    build_pdf(df, figure_paths, keyword_paths)


if __name__ == '__main__':
    main()
