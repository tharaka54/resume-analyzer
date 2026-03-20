from datetime import datetime, timezone
from bson import ObjectId
from app.models.db import get_db

def _serialize(obj: dict) -> dict:
    if obj:
        obj["_id"] = str(obj["_id"])
    return obj

def save_job_quiz_pool(job_id: str, questions: list) -> bool:
    """Save the AI generated 20 questions for a specific job."""
    try:
        db = get_db()
        db.quizzes.update_one(
            {"job_id": job_id},
            {"$set": {
                "job_id": job_id,
                "questions": questions,
                "updated_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        return True
    except Exception:
        return False

def get_job_quiz_pool(job_id: str) -> dict | None:
    try:
        db = get_db()
        return _serialize(db.quizzes.find_one({"job_id": job_id}))
    except Exception:
        return None

def track_quiz_attempt(job_id: str, user_id: str, score: int, pass_status: bool, tab_switches: int) -> dict:
    """Save an applicant's attempt."""
    db = get_db()
    result = db.quiz_attempts.insert_one({
        "job_id": job_id,
        "user_id": user_id,
        "score": score,
        "passed": pass_status,
        "tab_switches": tab_switches,
        "created_at": datetime.now(timezone.utc)
    })
    return {"_id": str(result.inserted_id), "job_id": job_id, "user_id": user_id, "score": score, "passed": pass_status}

def get_recent_attempts(job_id: str, user_id: str) -> list:
    try:
        db = get_db()
        attempts = db.quiz_attempts.find({"job_id": job_id, "user_id": user_id}).sort("created_at", -1)
        return [_serialize(a) for a in attempts]
    except Exception:
        return []
