"""
app/routes/jobs.py — Job Posting CRUD API
Blueprint: /jobs
All routes require JWT authentication.
"""

from flask import Blueprint, request, jsonify, g
from werkzeug.utils import secure_filename
import os
import uuid
from app.middleware.auth_middleware import require_auth
from app.models.job import create_job, get_jobs_by_user, get_job_by_id, update_job, delete_job, get_all_public_jobs, get_job_by_id_public
from app.security.input_sanitizer import (
    sanitize_job_payload, NoSQLInjectionError, InputSanitizationError
)
from app.extensions import limiter

jobs_bp = Blueprint("jobs", __name__)

LOGOS_DIR = os.path.join("app", "static", "img", "logos")
os.makedirs(LOGOS_DIR, exist_ok=True)

def allowed_logo_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}


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
@limiter.limit("10 per hour")           # NFR #9 — prevent spam job postings
def create():
    """
    POST /jobs/
    Create a new job posting.
    """
    # If FormData was sent, use request.form. Otherwise fallback to JSON.
    data = request.form.to_dict() if request.form else request.get_json() or {}

    # ── Sanitize + NoSQL injection guard ─────────────────────────────────
    try:
        data = sanitize_job_payload(data)
    except NoSQLInjectionError as e:
        return jsonify({"error": str(e), "layer": "Input Security: NoSQL Guard"}), 400
    except InputSanitizationError as e:
        return jsonify({"error": str(e), "layer": "Input Security: Sanitizer"}), 400

    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    company = data.get("company", "").strip()
    location = data.get("location", "").strip()
    job_type = data.get("job_type", "").strip()
    required_skills = data.get("required_skills", "").strip()
    logo_url = data.get("logo_url", "").strip()

    # Handle logo file upload
    if 'logo_file' in request.files:
        file = request.files['logo_file']
        if file and file.filename and allowed_logo_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            file_path = os.path.join(LOGOS_DIR, filename)
            file.save(file_path)
            logo_url = f"/static/img/logos/{filename}"

    if not title or not description:
        return jsonify({"error": "title and description are required"}), 400

    if len(description) < 50:
        return jsonify({"error": "Job description must be at least 50 characters"}), 400

    job = create_job(user_id=g.user_id, title=title, description=description, company=company, location=location, job_type=job_type, required_skills=required_skills, logo_url=logo_url)
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
    data = request.form.to_dict() if request.form else request.get_json() or {}

    # ── Sanitize + NoSQL injection guard ─────────────────────────────────
    try:
        data = sanitize_job_payload(data)
    except NoSQLInjectionError as e:
        return jsonify({"error": str(e), "layer": "Input Security: NoSQL Guard"}), 400
    except InputSanitizationError as e:
        return jsonify({"error": str(e), "layer": "Input Security: Sanitizer"}), 400

    updates = {}

    for field in ["title", "company", "location", "job_type", "required_skills", "logo_url"]:
        if field in data:
            updates[field] = data[field].strip()
            
    # Handle optional logo file upload on edit
    if 'logo_file' in request.files:
        file = request.files['logo_file']
        if file and file.filename and allowed_logo_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            file_path = os.path.join(LOGOS_DIR, filename)
            file.save(file_path)
            updates["logo_url"] = f"/static/img/logos/{filename}"
            
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
