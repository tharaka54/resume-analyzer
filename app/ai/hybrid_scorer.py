"""
app/ai/hybrid_scorer.py — Final Hybrid Score Computation
Combines TF-IDF and BERT scores:
    Final Score = TF-IDF(40%) + BERT(60%)

Rationale:
  - TF-IDF (40%): Fast, exact keyword matching — ensures specific required
    technologies like "React", "MongoDB" are explicitly present.
  - BERT (60%): Semantic similarity — catches paraphrased experience, role
    alignment, and conceptual overlap without keyword dependency.
"""

from dataclasses import dataclass, field
from app.ai.tfidf_model import compute_tfidf_score
from app.ai.bert_model import compute_bert_score, get_highly_matched_sentences
from app.ai.skill_extractor import extract_skills, compute_skill_gap

TFIDF_WEIGHT = 0.32
BERT_WEIGHT = 0.48
QUIZ_WEIGHT = 0.20


@dataclass
class ScoringResult:
    quiz_score: float # out of 1.0 (e.g. 70% is 0.7)
    tfidf_score: float
    bert_score: float
    hybrid_score: float
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    bert_matched_sentences: list[str] = field(default_factory=list)
    skill_match_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "quiz_score": round(self.quiz_score * 100, 2),
            "tfidf_score": round(self.tfidf_score * 100, 2),
            "bert_score": round(self.bert_score * 100, 2),
            "hybrid_score": round(self.hybrid_score * 100, 2),
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "bert_matched_sentences": self.bert_matched_sentences,
            "skill_match_pct": round(self.skill_match_pct, 2),
        }


def score_resume(job_description: str, resume_text: str, quiz_score: float = 0.0) -> ScoringResult:
    """
    Full scoring pipeline for a single resume.
    """
    raw_tfidf = compute_tfidf_score(job_description, resume_text)
    raw_bert = compute_bert_score(job_description, resume_text)

    tfidf = min(1.0, raw_tfidf * 3.0)
    bert = min(1.0, raw_bert ** 0.5)

    hybrid = round(QUIZ_WEIGHT * quiz_score + TFIDF_WEIGHT * tfidf + BERT_WEIGHT * bert, 4)

    # Skill gap analysis
    jd_skills = extract_skills(job_description)
    cv_skills = extract_skills(resume_text)
    matched, missing = compute_skill_gap(jd_skills, cv_skills)

    skill_match_pct = (len(matched) / len(jd_skills) * 100) if jd_skills else 0.0

    bert_matched_sentences = get_highly_matched_sentences(job_description, resume_text, threshold=0.45)

    return ScoringResult(
        quiz_score=quiz_score,
        tfidf_score=tfidf,
        bert_score=bert,
        hybrid_score=hybrid,
        matched_skills=matched,
        missing_skills=missing,
        bert_matched_sentences=bert_matched_sentences,
        skill_match_pct=skill_match_pct,
    )
