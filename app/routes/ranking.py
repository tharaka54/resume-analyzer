"""
app/routes/ranking.py — AI Ranking & CSV Export API
Blueprint: /ranking
"""

import csv
import io
from functools import wraps
from flask import Blueprint, request, jsonify, g, Response
from app.middleware.auth_middleware import require_auth
from app.models.job import get_job_by_id
from app.models.resume import get_resumes_by_job, update_resume_scores
from app.ai.hybrid_scorer import score_resume
from app.ai.llm_explainer import generate_explanation
from app.utils.jwt_helper import decode_token
import jwt

ranking_bp = Blueprint("ranking", __name__)


def _require_auth_or_token(f):
    """
    Auth decorator that accepts a JWT via:
      1. Authorization: Bearer <token>  header  (API / fetch calls)
      2. ?token=<token>                  query   (browser file downloads / <a href> clicks)

    Browser-initiated file downloads cannot set custom headers, so the
    frontend passes the access token as a query param instead.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. Try Authorization header first
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
        else:
            # 2. Fall back to ?token= query parameter (for browser downloads)
            token = request.args.get("token", "")

        if not token:
            return jsonify({"error": "Authentication required. Pass a Bearer token or ?token= query param."}), 401

        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                return jsonify({"error": "Invalid token type — use access token"}), 401
            g.user_id = payload["sub"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired — please log in again"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"error": f"Invalid token: {str(e)}"}), 401

        return f(*args, **kwargs)
    return decorated


@ranking_bp.route("/<job_id>", methods=["POST"])
@require_auth
def run_ranking(job_id):
    """
    POST /ranking/<job_id>
    Trigger AI scoring for all unranked resumes in a job.

    Hybrid scoring formula (Gantt task 4.29):
      Final Score = Quiz (20%) + TF-IDF (32%) + BERT (48%)

    Per resume pipeline:
      1. Quiz score lookup (from quiz_attempts collection)
      2. TF-IDF keyword match score
      3. BERT semantic similarity score
      4. Hybrid score = 20% quiz + 32% TF-IDF + 48% BERT
      5. spaCy NER skill gap analysis (matched + missing skills)
      6. Random Forest ML hiring prediction (supplementary, not in ranking formula)
      7. Gemini LLM plain-English explanation

    Returns ranked list sorted by hybrid score descending.
    """
    job = get_job_by_id(job_id, g.user_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    try:
        resumes = get_resumes_by_job(job_id)
    except Exception:
        return jsonify({"error": "Failed to retrieve resumes. Please try again."}), 500

    if not resumes:
        return jsonify({"error": "No resumes uploaded for this job"}), 400

    job_description = job.get("description", "")
    job_title = job.get("title", "Unknown Position")
    results = []

    from app.models.quiz import get_recent_attempts
    
    for resume in resumes:
        resume_id = resume["_id"]
        raw_text = resume.get("raw_text", "")
        candidate_name = resume.get("candidate_name", "Unknown")
        user_id = resume.get("user_id")

        if not raw_text:
            continue

        # Fetch quiz score for this user/job
        attempts = get_recent_attempts(job_id, user_id)
        best_score = max([a["score"] for a in attempts]) if attempts else 0
        quiz_pct = best_score / 15.0  # e.g., 12/15 becomes 0.8

        # Run AI scoring
        result = score_resume(job_description, raw_text, quiz_score=quiz_pct)

        # Generate plain-English explanation
        explanation = generate_explanation(
            candidate_name=candidate_name,
            job_title=job_title,
            job_description=job_description,
            resume_text=raw_text,
            hybrid_score=result.hybrid_score * 100,
            matched_skills=result.matched_skills,
            missing_skills=result.missing_skills,
        )

        # Persist scores to DB
        update_resume_scores(
            resume_id=resume_id,
            quiz_score=round(result.quiz_score * 100, 2),
            tfidf_score=round(result.tfidf_score * 100, 2),
            bert_score=round(result.bert_score * 100, 2),
            hybrid_score=round(result.hybrid_score * 100, 2),
            matched_skills=result.matched_skills,
            missing_skills=result.missing_skills,
            bert_matched_sentences=result.bert_matched_sentences,
            skill_match_pct=result.skill_match_pct,
            llm_explanation=explanation,
            ml_prediction=result.ml_prediction,
            ml_probability=round(result.ml_probability, 2)
        )

        results.append({
            "resume_id": resume_id,
            "candidate_name": candidate_name,
            "original_filename": resume.get("original_filename"),
            **result.to_dict(),
            "llm_explanation": explanation,
        })

    # Sort by hybrid score descending
    results.sort(key=lambda x: x["hybrid_score"], reverse=True)

    return jsonify({
        "job_id": job_id,
        "job_title": job_title,
        "total_ranked": len(results),
        "results": results,
    }), 200


@ranking_bp.route("/<job_id>/results", methods=["GET"])
@require_auth
def get_results(job_id):
    """
    GET /ranking/<job_id>/results
    Retrieve already-computed ranking results from MongoDB.
    """
    job = get_job_by_id(job_id, g.user_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    try:
        resumes = get_resumes_by_job(job_id)
    except Exception:
        return jsonify({"error": "Failed to retrieve results. Please try again."}), 500

    ranked = [r for r in resumes if r.get("ranked")]
    # Strip raw text for smaller response
    for r in ranked:
        r.pop("raw_text", None)

    ranked.sort(key=lambda x: x.get("hybrid_score") or 0, reverse=True)
    return jsonify({"results": ranked, "total": len(ranked)}), 200


@ranking_bp.route("/<job_id>/export/csv", methods=["GET"])
@_require_auth_or_token          # supports both header (API) and ?token= (browser download)
def export_csv(job_id):
    """
    GET /ranking/<job_id>/export/csv
    Export ranking results as a downloadable CSV file.

    Authentication:
      - API clients:   Authorization: Bearer <token>  header
      - Browser links: ?token=<access_token>           query param
        (browsers cannot send custom headers on direct navigation / <a href> clicks)
    """
    job = get_job_by_id(job_id, g.user_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    resumes = get_resumes_by_job(job_id)
    ranked = sorted(
        [r for r in resumes if r.get("ranked")],
        key=lambda x: x.get("hybrid_score") or 0,
        reverse=True,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Rank", "Candidate Name", "Original File",
        "Hybrid Score (%)", "Quiz Score (%)", "TF-IDF Score (%)", "BERT Score (%)",
        "Skill Match (%)", "Matched Skills", "Missing Skills",
        "ML Prediction", "ML Probability",
        "AI Explanation",
    ])

    for rank, r in enumerate(ranked, start=1):
        writer.writerow([
            rank,
            r.get("candidate_name", "Unknown"),
            r.get("original_filename", ""),
            r.get("hybrid_score", ""),
            r.get("quiz_score", ""),
            r.get("tfidf_score", ""),
            r.get("bert_score", ""),
            r.get("skill_match_pct", ""),
            "; ".join(r.get("matched_skills", [])),
            "; ".join(r.get("missing_skills", [])),
            r.get("ml_prediction", "Unknown"),
            r.get("ml_probability", 0.0),
            r.get("llm_explanation", ""),
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=ranking_{job_id}.csv"},
    )
