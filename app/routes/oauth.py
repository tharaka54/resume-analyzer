"""
app/routes/oauth.py — Google OAuth 2.0 Login & Callback
Blueprint: /auth
"""

import os
import secrets
import requests
from flask import Blueprint, redirect, request, jsonify, session, current_app
from urllib.parse import urlencode

from app.models.user import upsert_user
from app.utils.jwt_helper import generate_access_token, generate_refresh_token
from app.extensions import limiter

oauth_bp = Blueprint("oauth", __name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@oauth_bp.route("/login")
@limiter.limit("3 per minute")          # NFR #9 — brute-force protection
def login():
    """
    GET /auth/login
    Redirects the user to Google's OAuth consent screen.
    Generates a CSRF state token stored in session.
    Rate-limited to 3 per minute per IP (NFR #9).
    """
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state

    params = {
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "redirect_uri": current_app.config["GOOGLE_REDIRECT_URI"],
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return redirect(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@oauth_bp.route("/callback")
@limiter.limit("3 per minute")          # NFR #9 — same cap as /login
def callback():
    """
    GET /auth/callback
    Google redirects here with ?code=... after user approves.
    Exchanges code for tokens, fetches user info, upserts DB record,
    and returns JWT tokens to the frontend.
    Rate-limited to 3 per minute per IP (NFR #9).
    """
    # CSRF state validation
    state = request.args.get("state", "")
    saved_state = session.pop("oauth_state", None)

    if not saved_state or state != saved_state:
        return jsonify({"error": "OAuth state mismatch — possible CSRF attack"}), 400

    code = request.args.get("code")
    if not code:
        error = request.args.get("error", "Unknown error")
        return jsonify({"error": f"OAuth denied: {error}"}), 400

    # Exchange authorization code for access token
    token_data = {
        "code": code,
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": current_app.config["GOOGLE_REDIRECT_URI"],
        "grant_type": "authorization_code",
    }

    token_response = requests.post(GOOGLE_TOKEN_URL, data=token_data, timeout=10)

    if not token_response.ok:
        return jsonify({"error": "Failed to exchange code for tokens"}), 400

    token_json = token_response.json()
    google_access_token = token_json.get("access_token")

    if not google_access_token:
        return jsonify({"error": "No access token received from Google"}), 400

    # Fetch user profile from Google
    userinfo_response = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {google_access_token}"},
        timeout=10,
    )

    if not userinfo_response.ok:
        return jsonify({"error": "Failed to fetch user info from Google"}), 400

    userinfo = userinfo_response.json()
    google_id = userinfo.get("sub")
    email = userinfo.get("email", "")
    name = userinfo.get("name", email.split("@")[0] if email else "Unknown")
    picture = userinfo.get("picture", "")

    if not google_id:
        return jsonify({"error": "Google did not return a user ID"}), 400

    # Upsert user into MongoDB
    user = upsert_user(google_id=google_id, email=email, name=name, picture=picture)
    user_id = str(user["_id"])

    # Issue our own JWT tokens
    access_token = generate_access_token(user_id)
    refresh_token = generate_refresh_token(user_id)

    # Redirect to frontend with tokens in query string
    frontend_url = request.host_url.rstrip("/")
    redirect_url = (
        f"{frontend_url}/?login_success=1"
        f"&access_token={access_token}"
        f"&refresh_token={refresh_token}"
        f"&name={name}"
        f"&email={email}"
        f"&picture={picture}"
    )
    return redirect(redirect_url)


@oauth_bp.route("/refresh", methods=["POST"])
@limiter.limit("5 per minute")          # NFR #9 — prevent token farming
def refresh():
    """
    POST /auth/refresh
    Body: { "refresh_token": "..." }
    Returns a new access token using a valid refresh token.
    Rate-limited to 5 per minute per IP (NFR #9).
    """
    data = request.get_json() or {}
    refresh_token = data.get("refresh_token", "")

    if not refresh_token:
        return jsonify({"error": "refresh_token is required"}), 400

    try:
        import jwt
        from app.utils.jwt_helper import decode_token, generate_access_token
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            return jsonify({"error": "Invalid token type"}), 401
        new_access = generate_access_token(payload["sub"])
        return jsonify({"access_token": new_access}), 200
    except Exception as e:
        return jsonify({"error": "Invalid or expired refresh token"}), 401


@oauth_bp.route("/me")
@limiter.limit("30 per minute")         # loose cap — prevents scraping
def me():
    """
    GET /auth/me
    Returns logged-in user info from the DB using the JWT in Authorization header.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth.split(" ", 1)[1]
    from app.utils.jwt_helper import get_user_id_from_token
    from app.models.user import find_user_by_id

    user_id = get_user_id_from_token(token)
    if not user_id:
        return jsonify({"error": "Invalid token"}), 401

    user = find_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": str(user["_id"]),
        "name": user.get("name"),
        "email": user.get("email"),
        "picture": user.get("picture"),
    }), 200
