"""
app/models/resume.py — Resume model (MongoDB)
Stores parsed CV text, scores, skill gaps, and LLM explanations.
"""

from datetime import datetime, timezone
from bson import ObjectId
from app.models.db import get_db


def _serialize(doc: dict) -> dict:
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


def create_resume(
    job_id: str,
    user_id: str,
    original_filename: str,
    safe_filename: str,
    raw_text: str,
) -> dict:
    """
    Store a newly uploaded and parsed resume.
    Scores are stored as None until ranking is performed.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "job_id": job_id,
        "user_id": user_id,
        "original_filename": original_filename,
        "safe_filename": safe_filename,
        "raw_text": raw_text,
        "candidate_name": _infer_name(raw_text, original_filename),
        "quiz_score": None,
        "tfidf_score": None,
        "bert_score": None,
        "hybrid_score": None,
        "matched_skills": [],
        "missing_skills": [],
        "bert_matched_sentences": [],
        "skill_match_pct": None,
        "llm_explanation": None,
        "status": "Under Review",  # Candidate tracking status
        "ranked": False,
        "uploaded_at": now,
        "ranked_at": None,
    }
    result = db.resumes.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


def get_resumes_by_job(job_id: str) -> list[dict]:
    """Return all resumes for a job, sorted by hybrid score descending."""
    db = get_db()
    cursor = db.resumes.find({"job_id": job_id}).sort("hybrid_score", -1)
    return [_serialize(r) for r in cursor]


def get_resumes_by_user(user_id: str) -> list[dict]:
    """Return all applications/resumes submitted by a candidate."""
    db = get_db()
    cursor = db.resumes.find({"user_id": user_id}).sort("uploaded_at", -1)
    return [_serialize(r) for r in cursor]


def update_resume_status(resume_id: str, new_status: str) -> bool:
    """Update application tracking status (Shortlisted, Selected, Rejected)."""
    try:
        db = get_db()
        result = db.resumes.update_one(
            {"_id": ObjectId(resume_id)},
            {"$set": {"status": new_status}}
        )
        return result.modified_count > 0
    except Exception:
        return False


def get_resume_by_id(resume_id: str) -> dict | None:
    """Fetch a single resume by ID."""
    try:
        db = get_db()
        doc = db.resumes.find_one({"_id": ObjectId(resume_id)})
        return _serialize(doc) if doc else None
    except Exception:
        return None


def update_resume_scores(
    resume_id: str,
    quiz_score: float,
    tfidf_score: float,
    bert_score: float,
    hybrid_score: float,
    matched_skills: list,
    missing_skills: list,
    bert_matched_sentences: list,
    skill_match_pct: float,
    llm_explanation: str,
) -> bool:
    """Update a resume with AI scores after ranking."""
    try:
        db = get_db()
        result = db.resumes.update_one(
            {"_id": ObjectId(resume_id)},
            {
                "$set": {
                    "quiz_score": quiz_score,
                    "tfidf_score": tfidf_score,
                    "bert_score": bert_score,
                    "hybrid_score": hybrid_score,
                    "matched_skills": matched_skills,
                    "missing_skills": missing_skills,
                    "bert_matched_sentences": bert_matched_sentences,
                    "skill_match_pct": skill_match_pct,
                    "llm_explanation": llm_explanation,
                    "ranked": True,
                    "ranked_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count > 0
    except Exception:
        return False


def delete_resume(resume_id: str) -> bool:
    """Delete a resume record."""
    try:
        db = get_db()
        result = db.resumes.delete_one({"_id": ObjectId(resume_id)})
        return result.deleted_count > 0
    except Exception:
        return False


def _infer_name(raw_text: str, filename: str) -> str:
    """
    Heuristically infer candidate name:
      1. First non-empty line of the resume (often the candidate's name)
      2. Fallback: filename without UUID extension
    """
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    if lines:
        first = lines[0]
        # Candidate name lines are typically 2-4 words, all alphabetical
        words = first.split()
        if 1 < len(words) <= 5 and all(w.replace("-", "").isalpha() for w in words):
            return first
    return "Unknown Candidate"
