"""
app/routes/jobs.py — Job Posting CRUD API
Blueprint: /jobs
All routes require JWT authentication.
"""

from flask import Blueprint, request, jsonify, g
from app.middleware.auth_middleware import require_auth
from app.models.job import create_job, get_jobs_by_user, get_job_by_id, update_job, delete_job, get_all_public_jobs, get_job_by_id_public

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.route("/public", methods=["GET"])
def list_public_jobs():
    """GET /jobs/public — Return all job postings for the public homepage."""
    jobs = get_all_public_jobs()
    return jsonify({"jobs": jobs}), 200

@jobs_bp.route("/public/<job_id>", methods=["GET"])
def get_public_job(job_id):
    """GET /jobs/public/<job_id> — Return a single job posting for public viewing."""
    job = get_job_by_id_public(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job), 200


@jobs_bp.route("/", methods=["POST"])
@require_auth
def create():
    """
    POST /jobs/
    Create a new job posting.
    """
    data = request.get_json() or {}
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    company = data.get("company", "").strip()
    location = data.get("location", "").strip()
    job_type = data.get("job_type", "").strip()
    required_skills = data.get("required_skills", "").strip()

    if not title or not description:
        return jsonify({"error": "title and description are required"}), 400

    if len(description) < 50:
        return jsonify({"error": "Job description must be at least 50 characters"}), 400

    job = create_job(user_id=g.user_id, title=title, description=description, company=company, location=location, job_type=job_type, required_skills=required_skills)
    job_id = job["_id"]

    # Generate the Quiz pool in background
    import threading
    from app.ai.quiz_generator import generate_quiz_for_job
    from app.models.quiz import save_job_quiz_pool

    def gen_quiz(jid, t, d, s):
        questions = generate_quiz_for_job(t, d, s)
        save_job_quiz_pool(jid, questions)

    threading.Thread(target=gen_quiz, args=(job_id, title, description, required_skills)).start()

    return jsonify(job), 201


@jobs_bp.route("/", methods=["GET"])
@require_auth
def list_jobs():
    """
    GET /jobs/
    Return all job postings for the authenticated user.
    """
    jobs = get_jobs_by_user(g.user_id)
    return jsonify({"jobs": jobs}), 200


@jobs_bp.route("/<job_id>", methods=["GET"])
@require_auth
def get_one(job_id):
    """GET /jobs/<job_id> — Retrieve a single job posting."""
    job = get_job_by_id(job_id, g.user_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job), 200


@jobs_bp.route("/<job_id>", methods=["PUT"])
@require_auth
def update(job_id):
    """
    PUT /jobs/<job_id>
    Update job attributes.
    """
    data = request.get_json() or {}
    updates = {}

    for field in ["title", "company", "location", "job_type", "required_skills"]:
        if field in data:
            updates[field] = data[field].strip()
            
    if "description" in data:
        if len(data["description"].strip()) < 50:
            return jsonify({"error": "Description must be at least 50 characters"}), 400
        updates["description"] = data["description"].strip()

    if not updates:
        return jsonify({"error": "No fields to update"}), 400

    success = update_job(job_id, g.user_id, updates)
    if not success:
        return jsonify({"error": "Job not found or no changes made"}), 404

    job = get_job_by_id(job_id, g.user_id)
    return jsonify(job), 200


@jobs_bp.route("/<job_id>", methods=["DELETE"])
@require_auth
def delete(job_id):
    """DELETE /jobs/<job_id> — Delete a job and all its resumes."""
    success = delete_job(job_id, g.user_id)
    if not success:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"message": "Job deleted successfully"}), 200
