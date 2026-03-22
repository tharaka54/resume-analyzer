from flask import Blueprint, request, jsonify, g
from datetime import datetime, timezone
import random
from app.middleware.auth_middleware import require_auth
from app.models.quiz import get_job_quiz_pool, track_quiz_attempt, get_recent_attempts

quiz_bp = Blueprint("quiz", __name__)


@quiz_bp.route("/<job_id>/start", methods=["GET"])
@require_auth
def start_quiz(job_id):
    """
    GET /quiz/<job_id>/start
    Serve a randomized subset of 10 questions to the user.
    """
    # Check cooldown/attempts
    attempts = get_recent_attempts(job_id, g.user_id)
    if len(attempts) >= 3:
        return jsonify({"error": "Maximum 2 attempts reached for this job."}), 403

    if attempts:
        last_attempt_time = attempts[0]["created_at"]
        if last_attempt_time.tzinfo is None:
            last_attempt_time = last_attempt_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if (now - last_attempt_time).total_seconds() < 86400: # 24 hours
            return jsonify({"error": "You must wait 24 hours before your next attempt."}), 403

    # Fetch pool
    pool_doc = get_job_quiz_pool(job_id)
    if not pool_doc or not pool_doc.get("questions"):
        return jsonify({"error": "Quiz is currently generating or unavailable. Please try again soon."}), 404

    pool = pool_doc["questions"]
    # Pick 10 random
    selected = random.sample(pool, min(15, len(pool)))

    # Strip correct_index before sending to client
    sanitized_quiz = []
    # Save a server-side session copy to grade later
    session_key = f"quiz_{job_id}_{g.user_id}"
    from app.models.db import get_db
    db = get_db()
    
    server_side_data = []
    
    for idx, q in enumerate(selected):
        # We also shuffle answers to prevent cheating
        opts = q["options"]
        correct_opt = opts[q["correct_index"]]
        new_opts = opts.copy()
        random.shuffle(new_opts)
        new_correct_idx = new_opts.index(correct_opt)
        
        server_side_data.append({
            "idx": idx,
            "correct_index": new_correct_idx
        })

        sanitized_quiz.append({
            "question": q["question"],
            "options": new_opts
        })

    # Save to db active_sessions collection
    db.quiz_sessions.update_one(
        {"user_id": g.user_id, "job_id": job_id},
        {"$set": {
            "started_at": datetime.now(timezone.utc),
            "answers": server_side_data
        }},
        upsert=True
    )

    return jsonify({"questions": sanitized_quiz, "timer_seconds": 600}), 200


@quiz_bp.route("/<job_id>/submit", methods=["POST"])
@require_auth
def submit_quiz(job_id):
    """
    POST /quiz/<job_id>/submit
    Body: { "answers": [0, 2, 1, 3...], "tab_switches": int }
    """
    data = request.get_json() or {}
    user_answers = data.get("answers", [])
    tab_switches = data.get("tab_switches", 0)

    from app.models.db import get_db
    db = get_db()
    
    session = db.quiz_sessions.find_one({"user_id": g.user_id, "job_id": job_id})
    if not session:
        return jsonify({"error": "No active quiz session found."}), 400

    started_at = session["started_at"]
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    time_spent = (datetime.now(timezone.utc) - started_at).total_seconds()
    
    # 5 min timer enforcement server side + 5 sec buffer
    if time_spent > 605:
        track_quiz_attempt(job_id, g.user_id, 0, False, tab_switches)
        db.quiz_sessions.delete_one({"_id": session["_id"]})
        return jsonify({"score": 0, "passed": False, "message": "Time limit exceeded. Scored zero."}), 200

    score = 0
    server_answers = session["answers"]
    
    for i, ans in enumerate(user_answers):
        if i < len(server_answers):
            if ans == server_answers[i]["correct_index"]:
                score += 1

    passed = score >= 12
    track_quiz_attempt(job_id, g.user_id, score, passed, tab_switches)
    db.quiz_sessions.delete_one({"_id": session["_id"]})

    return jsonify({"score": score, "passed": passed}), 200

@quiz_bp.route("/<job_id>/view", methods=["GET"])
@require_auth
def view_quiz(job_id):
    """
    GET /quiz/<job_id>/view
    Allow recruiter to view the generated quiz.
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
def regenerate_quiz(job_id):
    """
    POST /quiz/<job_id>/regenerate
    Allow recruiter to regenerate the quiz.
    """
    from app.models.job import get_job_by_id
    job = get_job_by_id(job_id, g.user_id)
    if not job:
        return jsonify({"error": "Unauthorized or Job not found"}), 403
        
    title = job.get("title", "")
    description = job.get("description", "")
    required_skills = job.get("required_skills", "")
    
    # Generate the Quiz pool in background
    import threading
    from app.ai.quiz_generator import generate_quiz_for_job
    from app.models.quiz import save_job_quiz_pool

    def gen_quiz(jid, t, d, s):
        questions = generate_quiz_for_job(t, d, s)
        save_job_quiz_pool(jid, questions)

    threading.Thread(target=gen_quiz, args=(job_id, title, description, required_skills)).start()
    return jsonify({"message": "Quiz regeneration started in background."}), 200
