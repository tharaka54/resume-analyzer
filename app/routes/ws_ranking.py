"""
app/routes/ws_ranking.py — WebSocket Live Ranking Progress
Blueprint: ws (no url_prefix — WebSocket path set explicitly)

Sends real-time JSON progress events to the React frontend via WebSocket
as each resume is being scored, allowing a live progress feed.

Client connects to: ws://localhost:5000/ws/ranking/<job_id>?token=<access_token>
"""

import json
from flask import request, current_app
from app import sock
from flask import Blueprint

from app.utils.jwt_helper import decode_token
from app.models.job import get_job_by_id
from app.models.resume import get_resumes_by_job, update_resume_scores
from app.ai.hybrid_scorer import score_resume
from app.ai.llm_explainer import generate_explanation

ws_bp = Blueprint("ws", __name__)


def _authenticate_ws(token: str) -> str | None:
    """Verify JWT from WebSocket query param. Returns user_id or None."""
    try:
        payload = decode_token(token)
        if payload.get("type") == "access":
            return payload.get("sub")
    except Exception:
        pass
    return None


def _send(ws, event: str, data: dict) -> None:
    """Send a JSON-serialised event over the WebSocket."""
    try:
        ws.send(json.dumps({"event": event, **data}))
    except Exception:
        pass


@sock.route("/ws/ranking/<job_id>")
def ws_ranking(ws, job_id: str):
    """
    WebSocket endpoint — streams ranking progress for a job.

    Events sent to client:
      { event: "connected",   total: N }
      { event: "progress",    index: i, total: N, candidate: str, score: float }
      { event: "result",      resume: {...} }
      { event: "complete",    total_ranked: N }
      { event: "error",       message: str }
    """
    # Authenticate via query param token
    token = request.args.get("token", "")
    user_id = _authenticate_ws(token)

    if not user_id:
        _send(ws, "error", {"message": "Unauthorized — invalid or missing token"})
        ws.close()
        return

    job = get_job_by_id(job_id, user_id)
    if not job:
        _send(ws, "error", {"message": "Job not found"})
        ws.close()
        return

    resumes = get_resumes_by_job(job_id)
    if not resumes:
        _send(ws, "error", {"message": "No resumes found for this job"})
        ws.close()
        return

    job_description = job.get("description", "")
    job_title = job.get("title", "Unknown")
    total = len(resumes)

    _send(ws, "connected", {"total": total, "job_title": job_title})

    ranked_results = []
    
    from app.models.quiz import get_recent_attempts

    for index, resume in enumerate(resumes, start=1):
        candidate_name = resume.get("candidate_name", "Unknown")
        raw_text = resume.get("raw_text", "")
        resume_id = resume["_id"]
        cv_user_id = resume.get("user_id")

        if not raw_text:
            _send(ws, "progress", {
                "index": index, "total": total,
                "candidate": candidate_name,
                "status": "skipped",
                "reason": "no text extracted",
            })
            continue

        if resume.get("ranked"):
            resume_result = {
                "resume_id": resume_id,
                "candidate_name": candidate_name,
                "original_filename": resume.get("original_filename"),
                "quiz_score": resume.get("quiz_score", 0) / 100.0,
                "tfidf_score": resume.get("tfidf_score", 0),
                "bert_score": resume.get("bert_score", 0),
                "hybrid_score": resume.get("hybrid_score", 0),
                "matched_skills": resume.get("matched_skills", []),
                "missing_skills": resume.get("missing_skills", []),
                "bert_matched_sentences": resume.get("bert_matched_sentences", []),
                "skill_match_pct": resume.get("skill_match_pct", 0),
                "ml_prediction": resume.get("ml_prediction", "Unknown"),
                "ml_probability": resume.get("ml_probability", 0.0),
                "llm_explanation": resume.get("llm_explanation", "")
            }
            ranked_results.append(resume_result)
            _send(ws, "result", {"resume": resume_result, "index": index, "total": total})
            continue

        # Notify frontend which resume is being processed
        _send(ws, "progress", {
            "index": index,
            "total": total,
            "candidate": candidate_name,
            "status": "scoring",
        })

        # Fetch quiz score
        attempts = get_recent_attempts(job_id, cv_user_id)
        best_score = max([a["score"] for a in attempts]) if attempts else 0
        quiz_pct = best_score / 10.0

        # Run AI scoring
        result = score_resume(job_description, raw_text, quiz_score=quiz_pct)

        _send(ws, "progress", {
            "index": index,
            "total": total,
            "candidate": candidate_name,
            "status": "generating_explanation",
        })

        explanation = generate_explanation(
            candidate_name=candidate_name,
            job_title=job_title,
            job_description=job_description,
            resume_text=raw_text,
            hybrid_score=result.hybrid_score * 100,
            matched_skills=result.matched_skills,
            missing_skills=result.missing_skills,
        )

        # Persist to MongoDB
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

        resume_result = {
            "resume_id": resume_id,
            "candidate_name": candidate_name,
            "original_filename": resume.get("original_filename"),
            **result.to_dict(),
            "llm_explanation": explanation,
        }
        ranked_results.append(resume_result)

        # Send full result for this resume
        _send(ws, "result", {"resume": resume_result, "index": index, "total": total})

    # Sort final results and send completion
    ranked_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
    _send(ws, "complete", {
        "total_ranked": len(ranked_results),
        "results": ranked_results,
    })
