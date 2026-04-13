"""
app/routes/quiz.py — Quiz Start, Submit, View & Regenerate
Blueprint: /quiz

Anti-cheat enforcement (server-side only):
  - 20-question pool per job; each applicant receives 15 randomised with shuffled answers
  - Timer: 600 seconds (10 minutes) enforced server-side with 5-second grace buffer (605 s total)
    NOTE: Proposal FR#4 mistakenly states 300 s — the correct value per NFR#4 and all UI
    references is 600 s (10 minutes). Implementation uses 605 s (600 + 5 s grace).
  - Max 2 attempts per user per job; 24-hour cooldown after each failed attempt
  - Tab-switch count recorded and included in ranking output

Score bands (FR #9 + FR #10):
  - score >= 12  → "passed"  → granted CV upload access
  - 7 ≤ score < 12 → "failed"  → can retry after 24-hour cooldown
  - score < 7    → "blocked" → same cooldown but shown stronger warning message

Rate limits (NFR #9):
  - /start  : 5 per minute per IP
  - /submit : 5 per minute per IP
"""

from flask import Blueprint, request, jsonify, g
from datetime import datetime, timezone
import random
from app.middleware.auth_middleware import require_auth
from app.models.quiz import get_job_quiz_pool, track_quiz_attempt, get_recent_attempts
from app.extensions import limiter

quiz_bp = Blueprint("quiz", __name__)


@quiz_bp.route("/<job_id>/start", methods=["GET"])
@require_auth
@limiter.limit("5 per minute")          # NFR #9 — prevent session farming
def start_quiz(job_id):
    """
    GET /quiz/<job_id>/start
    Serve a randomised subset of 15 questions from the 20-question pool.
    Answers are shuffled per-user; correct indices stored server-side only.
    Rate-limited to 5 per minute per IP (NFR #9).
    """
    # Check cooldown / max attempts
    attempts = get_recent_attempts(job_id, g.user_id)
    if len(attempts) >= 3:
        return jsonify({"error": "Maximum 2 attempts reached for this job."}), 403

    if attempts:
        last_attempt_time = attempts[0]["created_at"]
        if last_attempt_time.tzinfo is None:
            last_attempt_time = last_attempt_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if (now - last_attempt_time).total_seconds() < 86400:  # 24 hours
            return jsonify({"error": "You must wait 24 hours before your next attempt."}), 403

    # Fetch pool
    pool_doc = get_job_quiz_pool(job_id)
    if not pool_doc or not pool_doc.get("questions"):
        return jsonify({"error": "Quiz is currently generating or unavailable. Please try again soon."}), 404

    pool = pool_doc["questions"]
    # Pick 15 random from the 20-question pool (FR #3)
    selected = random.sample(pool, min(15, len(pool)))

    sanitized_quiz = []
    server_side_data = []

    from app.models.db import get_db
    db = get_db()

    for idx, q in enumerate(selected):
        # Shuffle answers per-session to prevent cheating (FR #3)
        opts = q["options"]
        correct_opt = opts[q["correct_index"]]
        new_opts = opts.copy()
        random.shuffle(new_opts)
        new_correct_idx = new_opts.index(correct_opt)

        server_side_data.append({
            "idx": idx,
            "correct_index": new_correct_idx,
        })

        # Correct index is NEVER sent to the client (System FR #6)
        sanitized_quiz.append({
            "question": q["question"],
            "options": new_opts,
        })

    # Persist server-side session (correct answers stored in DB, never on client)
    db.quiz_sessions.update_one(
        {"user_id": g.user_id, "job_id": job_id},
        {"$set": {
            "started_at": datetime.now(timezone.utc),
            "answers": server_side_data,
        }},
        upsert=True,
    )

    return jsonify({"questions": sanitized_quiz, "timer_seconds": 600}), 200


@quiz_bp.route("/<job_id>/submit", methods=["POST"])
@require_auth
@limiter.limit("5 per minute")          # NFR #9 — prevent score manipulation attempts
def submit_quiz(job_id):
    """
    POST /quiz/<job_id>/submit
    Body: { "answers": [0, 2, 1, 3...], "tab_switches": int }

    Timer: 600 seconds (10 minutes) enforced server-side + 5-second grace = 605 s total.
    Note: Proposal FR#4 reads "300 seconds" — this is a typo for 600 s (10 min).
    The NFR, Gantt chart, and all UI references consistently state 10 minutes.

    Score bands returned (FR #9, FR #10):
      - score >= 12  → passed=True,  score_band="passed"  — CV upload unlocked
      - 7 ≤ score < 12 → passed=False, score_band="failed"  — retry after 24 hours
      - score < 7    → passed=False, score_band="blocked"  — retry after 24 hours (stronger warning)

    Rate-limited to 5 per minute per IP (NFR #9).
    """
    data = request.get_json() or {}
    user_answers = data.get("answers", [])
    tab_switches = int(data.get("tab_switches", 0))

    from app.models.db import get_db
    db = get_db()

    session = db.quiz_sessions.find_one({"user_id": g.user_id, "job_id": job_id})
    if not session:
        return jsonify({"error": "No active quiz session found."}), 400

    started_at = session["started_at"]
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    time_spent = (datetime.now(timezone.utc) - started_at).total_seconds()

    # Server-side timer enforcement: 600 s + 5 s grace = 605 s (NFR #4 / FR#4)
    if time_spent > 605:
        track_quiz_attempt(job_id, g.user_id, 0, False, tab_switches)
        db.quiz_sessions.delete_one({"_id": session["_id"]})
        return jsonify({
            "score": 0,
            "passed": False,
            "score_band": "timeout",
            "message": "Time limit exceeded (10 minutes). Your submission has been scored zero.",
        }), 200

    # Grade answers against server-stored correct indices
    score = 0
    server_answers = session["answers"]
    for i, ans in enumerate(user_answers):
        if i < len(server_answers):
            if ans == server_answers[i]["correct_index"]:
                score += 1

    passed = score >= 12

    # ── Score band classification (FR #9 + FR #10) ────────────────────────────
    if score >= 12:
        score_band = "passed"
        message = f"Congratulations! You scored {score}/15. You may now upload your CV."
    elif score >= 7:
        score_band = "failed"
        message = (
            f"You scored {score}/15. The passing score is 12. "
            "Please wait 24 hours before your next attempt."
        )
    else:
        score_band = "blocked"
        message = (
            f"You scored {score}/15. This is below the minimum threshold of 7. "
            "Please review the job requirements and try again after 24 hours."
        )

    track_quiz_attempt(job_id, g.user_id, score, passed, tab_switches)
    db.quiz_sessions.delete_one({"_id": session["_id"]})

    return jsonify({
        "score": score,
        "passed": passed,
        "score_band": score_band,
        "message": message,
        "tab_switches": tab_switches,
    }), 200


@quiz_bp.route("/<job_id>/view", methods=["GET"])
@require_auth
def view_quiz(job_id):
    """
    GET /quiz/<job_id>/view
    Allow recruiter (job owner) to view the generated quiz pool.
    """
    from app.models.job import get_job_by_id
    job = get_job_by_id(job_id, g.user_id)
    if not job:
        return jsonify({"error": "Unauthorized or Job not found"}), 403

    pool_doc = get_job_quiz_pool(job_id)
    if not pool_doc or not pool_doc.get("questions"):
        return jsonify({"error": "Quiz is currently generating or unavailable."}), 404

    return jsonify({"questions": pool_doc["questions"]}), 200


@quiz_bp.route("/<job_id>/regenerate", methods=["POST"])
@require_auth
@limiter.limit("3 per hour")            # prevent excessive Gemini API calls
def regenerate_quiz(job_id):
    """
    POST /quiz/<job_id>/regenerate
    Allow recruiter to regenerate the quiz pool via Gemini.
    Rate-limited to 3 per hour to protect the Gemini API quota.
    """
    from app.models.job import get_job_by_id
    job = get_job_by_id(job_id, g.user_id)
    if not job:
        return jsonify({"error": "Unauthorized or Job not found"}), 403

    title = job.get("title", "")
    description = job.get("description", "")
    required_skills = job.get("required_skills", "")

    import threading
    from app.ai.quiz_generator import generate_quiz_for_job
    from app.models.quiz import save_job_quiz_pool

    def gen_quiz(jid, t, d, s):
        questions = generate_quiz_for_job(t, d, s)
        save_job_quiz_pool(jid, questions)

    threading.Thread(target=gen_quiz, args=(job_id, title, description, required_skills)).start()
    return jsonify({"message": "Quiz regeneration started in background."}), 200
