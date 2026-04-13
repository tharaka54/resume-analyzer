"""
app/routes/resumes.py — Resume Upload & Retrieval API
Blueprint: /resumes
All routes require JWT authentication.

Security Pipeline:
  Layer 1 : validate_upload       — extension, MIME, size
  Layer 2a: verify_pdf_magic_bytes — binary PDF header check
  Layer 2b: inspect_pdf           — PyMuPDF deep scan + text extraction
  Layer 3 : sanitize_filename     — UUID rename + path traversal guard
  Layer 4 : input_sanitizer       — HTML strip + NoSQL injection guard
  Layer 5 : antivirus             — entropy heuristic + VirusTotal API
"""

import os
from flask import Blueprint, request, jsonify, g, current_app

from app.middleware.auth_middleware import require_auth
from app.models.job import get_job_by_id, get_job_by_id_public, increment_resume_count
from app.models.resume import (
    create_resume, get_resumes_by_job, get_resume_by_id, delete_resume,
    get_resumes_by_user, update_resume_status
)

from app.security.upload_security import (
    validate_upload, FileValidationError,
    verify_pdf_magic_bytes, MagicBytesError,
    inspect_pdf, PDFInspectionError,
    sanitize_filename, get_safe_filepath,
)
from app.security.antivirus import scan_file_for_malware, AntivirusError
from app.security.input_sanitizer import sanitize_status_payload, NoSQLInjectionError, InputSanitizationError
from app.extensions import limiter

resumes_bp = Blueprint("resumes", __name__)


@resumes_bp.route("/<job_id>/upload", methods=["POST"])
@require_auth
@limiter.limit("20 per hour")           # NFR #9 — prevents spam; allows retries on error
def upload(job_id):
    """
    POST /resumes/<job_id>/upload
    Multipart form upload: file=<PDF>

    Runs the full 4-layer security validation pipeline before storing.
    """
    # Verify job exists
    job = get_job_by_id_public(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if "resume" in request.files:
        file = request.files["resume"]
    elif "file" in request.files:
        file = request.files["file"]
    else:
        return jsonify({"error": "No file part in the request (expected 'resume' or 'file')"}), 400

    # ── Layer 1: Extension + MIME + Size ─────────────────────────────────────
    try:
        validate_upload(file)
    except FileValidationError as e:
        return jsonify({"error": str(e), "layer": "Layer 1: File Validation"}), 400

    # Read file bytes for deeper inspection
    file_bytes = file.read()

    # ── Layer 2a: Magic Bytes ─────────────────────────────────────────────────
    try:
        verify_pdf_magic_bytes(file_bytes)
    except MagicBytesError as e:
        return jsonify({"error": str(e), "layer": "Layer 2a: Magic Bytes"}), 400

    # ── Layer 2b: Deep PDF Inspection + Text Extraction ───────────────────────
    try:
        raw_text = inspect_pdf(file_bytes)
    except PDFInspectionError as e:
        return jsonify({"error": str(e), "layer": "Layer 2b: PDF Inspector"}), 400

    # ── Layer 5: Antivirus / VirusTotal Scan ──────────────────────────────────
    try:
        scan_file_for_malware(file_bytes)
    except AntivirusError as e:
        return jsonify({"error": str(e), "layer": "Layer 5: Antivirus"}), 400

    # ── Layer 3: Filename Sanitization ────────────────────────────────────────
    original_filename = file.filename
    safe_filename = sanitize_filename(original_filename)
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    filepath = get_safe_filepath(upload_folder, safe_filename)

    # Save the raw bytes (already read) to disk
    with open(filepath, "wb") as f:
        f.write(file_bytes)

    # Store resume record in MongoDB
    resume = create_resume(
        job_id=job_id,
        user_id=g.user_id,
        original_filename=original_filename,
        safe_filename=safe_filename,
        raw_text=raw_text,
    )
    increment_resume_count(job_id)

    return jsonify({
        "message": "Resume uploaded and parsed successfully",
        "resume_id": resume["_id"],
        "candidate_name": resume["candidate_name"],
        "original_filename": original_filename,
        "text_length": len(raw_text),
    }), 201


@resumes_bp.route("/my-applications", methods=["GET"])
@require_auth
def my_applications():
    """
    GET /resumes/my-applications — Candidate dashboard (FR #12).

    Returns all applications with two status fields:
      - journey_status  : applicant's pipeline stage (FR #12 / Task 4.37)
                          "Quiz Passed, CV Uploaded, Under Review"
      - status          : recruiter's decision ("Shortlisted", "Selected", "Rejected", etc.)
    """
    resumes = get_resumes_by_user(g.user_id)
    for r in resumes:
        r.pop("raw_text", None)
        job = get_job_by_id_public(r.get("job_id"))
        if job:
            r["job_title"] = job.get("title")
            r["company"] = job.get("company")
        # ── FIX-05: Build human-readable journey_status (FR #12 / Task 4.37) ──
        # journey_status stored on the document (set at create time).
        # Fall back to a computed label if the field pre-dates this fix.
        if not r.get("journey_status"):
            r["journey_status"] = "Quiz Passed → CV Uploaded → Under Review"
    return jsonify(resumes), 200


@resumes_bp.route("/detail/<resume_id>/status", methods=["PUT"])
@require_auth
def update_status(resume_id):
    """PUT /resumes/detail/<resume_id>/status - Recruiter updates status"""
    data = request.get_json() or {}

    # ── Layer 4: Sanitize status input + NoSQL guard ───────────────────────
    try:
        new_status = sanitize_status_payload(data)
    except (NoSQLInjectionError, InputSanitizationError) as e:
        return jsonify({"error": str(e), "layer": "Input Security"}), 400

    if new_status not in ["Under Review", "Shortlisted", "Selected", "Rejected"]:
        return jsonify({"error": "Invalid status"}), 400

    resume = get_resume_by_id(resume_id)
    if not resume:
        return jsonify({"error": "Resume not found"}), 404

    # Require job owner
    job = get_job_by_id(resume.get("job_id"), g.user_id)
    if not job:
        return jsonify({"error": "Unauthorized"}), 403

    success = update_resume_status(resume_id, new_status)
    if success:
        return jsonify({"message": f"Status updated to {new_status}"}), 200
    return jsonify({"error": "Update failed"}), 500


@resumes_bp.route("/<job_id>", methods=["GET"])
@require_auth
def list_resumes(job_id):
    """GET /resumes/<job_id> — List all resumes for a job, sorted by score."""
    job = get_job_by_id(job_id, g.user_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    resumes = get_resumes_by_job(job_id)
    # Strip raw_text from list view for smaller payload
    for r in resumes:
        r.pop("raw_text", None)

    return jsonify(resumes), 200


@resumes_bp.route("/detail/<resume_id>", methods=["GET"])
@require_auth
def get_one(resume_id):
    """GET /resumes/detail/<resume_id> — Full resume detail including raw_text."""
    resume = get_resume_by_id(resume_id)
    if not resume:
        return jsonify({"error": "Resume not found"}), 404

    # Verify ownership or if the user is the job owner (recruiter)
    is_resume_owner = resume.get("user_id") == g.user_id
    
    # Check if they own the job
    job = get_job_by_id(resume.get("job_id"), g.user_id) if not is_resume_owner else None
    is_job_owner = job is not None

    if not is_resume_owner and not is_job_owner:
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify(resume), 200


@resumes_bp.route("/detail/<resume_id>", methods=["DELETE"])
@require_auth
def delete_one(resume_id):
    """DELETE /resumes/detail/<resume_id> — Delete a resume record."""
    resume = get_resume_by_id(resume_id)
    if not resume:
        return jsonify({"error": "Resume not found"}), 404

    if resume.get("user_id") != g.user_id:
        return jsonify({"error": "Unauthorized"}), 403

    # Delete file from disk
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    filepath = os.path.join(upload_folder, resume.get("safe_filename", ""))
    if os.path.isfile(filepath):
        os.remove(filepath)

    delete_resume(resume_id)
    return jsonify({"message": "Resume deleted"}), 200
