"""
app/middleware/auth_middleware.py — JWT Verification Middleware
Decorator for protecting routes — verifies Bearer token in Authorization header.
"""

from functools import wraps
from flask import request, jsonify, g
from app.utils.jwt_helper import decode_token
import jwt


def require_auth(f):
    """
    Route decorator that:
      1. Extracts the Bearer token from the Authorization header.
      2. Verifies the JWT signature and expiry.
      3. Attaches the decoded user_id to Flask's g context.

    Usage:
        @app.route("/protected")
        @require_auth
        def protected_route():
            user_id = g.user_id
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401

        token = auth_header.split(" ", 1)[1]

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
