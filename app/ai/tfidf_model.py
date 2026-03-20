"""
app/ai/tfidf_model.py — TF-IDF Vectorizer + Cosine Similarity Scoring
Provides the keyword-match component (40%) of the hybrid score.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from app.ai.preprocess import clean_text


def compute_tfidf_score(job_description: str, resume_text: str) -> float:
    """
    Vectorize job description and resume with TF-IDF, then return
    cosine similarity as a score in [0.0, 1.0].

    Args:
        job_description: Raw job posting text.
        resume_text:     Raw resume text.

    Returns:
        Float score between 0.0 (no match) and 1.0 (perfect match).
    """
    cleaned_jd = clean_text(job_description)
    cleaned_cv = clean_text(resume_text)

    if not cleaned_jd.strip() or not cleaned_cv.strip():
        return 0.0

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),   # unigrams + bigrams for richer matching
        max_features=10_000,
        sublinear_tf=True,    # apply log normalization
    )

    try:
        tfidf_matrix = vectorizer.fit_transform([cleaned_jd, cleaned_cv])
        score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return float(np.clip(score, 0.0, 1.0))
    except ValueError:
        # Handles edge case where vocabulary is empty
        return 0.0


def get_top_keywords(job_description: str, top_n: int = 20) -> list[str]:
    """
    Return the top N TF-IDF weighted keywords from the job description.
    Useful for displaying what keywords the system is scoring against.

    Args:
        job_description: Raw job posting text.
        top_n:           Number of keywords to return.

    Returns:
        List of keyword strings, sorted by importance.
    """
    cleaned_jd = clean_text(job_description)
    if not cleaned_jd.strip():
        return []

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=10_000, sublinear_tf=True)
    try:
        tfidf_matrix = vectorizer.fit_transform([cleaned_jd])
        feature_names = vectorizer.get_feature_names_out()
        scores = tfidf_matrix.toarray()[0]
        top_indices = np.argsort(scores)[::-1][:top_n]
        return [feature_names[i] for i in top_indices if scores[i] > 0]
    except Exception:
        return []
