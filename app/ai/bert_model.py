"""
app/ai/bert_model.py — BERT Sentence-Transformers Semantic Similarity
Provides the semantic-match component (60%) of the hybrid score.

Uses 'all-MiniLM-L6-v2' — a CPU-compatible sentence-transformer model
that balances accuracy and inference speed (~80ms/resume on CPU).
"""

from functools import lru_cache
import numpy as np
from sentence_transformers import SentenceTransformer, util

# Model is ~90 MB and loaded once at import time (or first call via cache)
MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    """Load and cache the sentence transformer model (singleton)."""
    print(f"[BERT] Loading sentence-transformer model: {MODEL_NAME}")
    return SentenceTransformer(MODEL_NAME)


def compute_bert_score(job_description: str, resume_text: str) -> float:
    """
    Encode job description and resume into dense embeddings, then compute
    cosine similarity as a semantic score in [0.0, 1.0].

    The model understands context and synonyms — 'software engineer' and
    'developer' will score highly even without exact keyword matches.

    Args:
        job_description: Raw job posting text (up to 512 tokens used).
        resume_text:     Raw resume text (up to 512 tokens used).

    Returns:
        Float score in [0.0, 1.0].
    """
    if not job_description.strip() or not resume_text.strip():
        return 0.0

    model = _load_model()

    # Truncate to 512 words to respect transformer limits
    jd_words = job_description.split()[:512]
    cv_words = resume_text.split()[:512]

    jd_truncated = " ".join(jd_words)
    cv_truncated = " ".join(cv_words)

    try:
        embeddings = model.encode(
            [jd_truncated, cv_truncated],
            convert_to_tensor=True,
            show_progress_bar=False,
        )
        score = util.cos_sim(embeddings[0], embeddings[1]).item()
        return float(np.clip(score, 0.0, 1.0))
    except Exception as e:
        print(f"[BERT] Encoding error: {e}")
        return 0.0


def batch_bert_scores(job_description: str, resume_texts: list[str]) -> list[float]:
    """
    Batch encode multiple resumes against a single job description.
    More efficient than calling compute_bert_score in a loop.

    Args:
        job_description: Raw job posting text.
        resume_texts:    List of raw resume texts.

    Returns:
        List of float scores corresponding to each resume.
    """
    if not resume_texts:
        return []

    model = _load_model()

    jd_truncated = " ".join(job_description.split()[:512])
    cv_truncated_list = [" ".join(cv.split()[:512]) for cv in resume_texts]

    all_texts = [jd_truncated] + cv_truncated_list

    try:
        embeddings = model.encode(all_texts, convert_to_tensor=True, show_progress_bar=False)
        jd_emb = embeddings[0]
        cv_embs = embeddings[1:]
        scores = [float(np.clip(util.cos_sim(jd_emb, cv_emb).item(), 0.0, 1.0)) for cv_emb in cv_embs]
        return scores
    except Exception as e:
        return [0.0] * len(resume_texts)

def get_highly_matched_sentences(job_description: str, resume_text: str, threshold: float = 0.45) -> list[str]:
    """
    Score each individual sentence in the resume against the job description.
    Returns a list of sentences that score above the threshold.
    """
    from app.ai.preprocess import tokenize_sentences
    
    sentences = tokenize_sentences(resume_text)
    if not sentences:
        return []

    scores = batch_bert_scores(job_description, sentences)
    matched = []
    
    for sentence, score in zip(sentences, scores):
        # Ignore extremely short sentences to reduce noise
        if score >= threshold and len(sentence.split()) > 3:
            matched.append(sentence)
            
    return matched
