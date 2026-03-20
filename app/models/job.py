"""
app/models/job.py — Job Posting model (MongoDB)
CRUD operations for job postings created by recruiters.
"""

from datetime import datetime, timezone
from bson import ObjectId
from app.models.db import get_db


def _serialize(job: dict) -> dict:
    """Convert ObjectId fields to strings for JSON serialization."""
    if job:
        job["_id"] = str(job["_id"])
    return job


def create_job(user_id: str, title: str, description: str, company: str = "", location: str = "", job_type: str = "", required_skills: str = "") -> dict:
    """Create a new job posting."""
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "title": title,
        "description": description,
        "company": company,
        "location": location,
        "job_type": job_type,
        "required_skills": required_skills,
        "created_at": now,
        "updated_at": now,
        "resume_count": 0,
    }
    result = db.jobs.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc

def get_all_public_jobs() -> list[dict]:
    """Return all jobs for public browsing."""
    try:
        db = get_db()
        jobs = db.jobs.find().sort("created_at", -1)
        return [_serialize(j) for j in jobs]
    except Exception:
        return []

def get_jobs_by_user(user_id: str) -> list[dict]:
    """Return all jobs created by a user, most recent first."""
    try:
        db = get_db()
        jobs = db.jobs.find({"user_id": user_id}).sort("created_at", -1)
        return [_serialize(j) for j in jobs]
    except Exception:
        return []

def get_job_by_id_public(job_id: str) -> dict | None:
    """Fetch a single job for public view."""
    try:
        db = get_db()
        job = db.jobs.find_one({"_id": ObjectId(job_id)})
        return _serialize(job) if job else None
    except Exception:
        return None

def get_job_by_id(job_id: str, user_id: str) -> dict | None:
    """Fetch a single job — verifies it belongs to the requesting user."""
    try:
        db = get_db()
        job = db.jobs.find_one({"_id": ObjectId(job_id), "user_id": user_id})
        return _serialize(job) if job else None
    except Exception:
        return None


def update_job(job_id: str, user_id: str, updates: dict) -> bool:
    """Update a job posting. Returns True if a document was modified."""
    try:
        db = get_db()
        updates["updated_at"] = datetime.now(timezone.utc)
        result = db.jobs.update_one(
            {"_id": ObjectId(job_id), "user_id": user_id},
            {"$set": updates},
        )
        return result.modified_count > 0
    except Exception:
        return False


def delete_job(job_id: str, user_id: str) -> bool:
    """Delete a job and all its associated resumes."""
    try:
        db = get_db()
        result = db.jobs.delete_one({"_id": ObjectId(job_id), "user_id": user_id})
        if result.deleted_count > 0:
            db.resumes.delete_many({"job_id": job_id})
            return True
        return False
    except Exception:
        return False


def increment_resume_count(job_id: str) -> None:
    """Increment the resume counter on a job posting."""
    try:
        db = get_db()
        db.jobs.update_one({"_id": ObjectId(job_id)}, {"$inc": {"resume_count": 1}})
    except Exception:
        pass
