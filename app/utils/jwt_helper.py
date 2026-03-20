"""
app/utils/jwt_helper.py — JWT Token Generation & Verification
Generates access (short-lived) and refresh (long-lived) tokens.
"""

import os
import jwt
from datetime import datetime, timedelta, timezone


def _secret() -> str:
    return os.getenv("JWT_SECRET_KEY", "jwt-secret-fallback")


def generate_access_token(user_id: str) -> str:
    """Generate a short-lived access token (default: 60 min)."""
    expires_minutes = int(os.getenv("JWT_ACCESS_EXPIRES_MINUTES", 60))
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def generate_refresh_token(user_id: str) -> str:
    """Generate a long-lived refresh token (default: 30 days)."""
    expires_days = int(os.getenv("JWT_REFRESH_EXPIRES_DAYS", 30))
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=expires_days),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.

    Returns:
        Decoded payload dict.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError:    Token is invalid.
    """
    return jwt.decode(token, _secret(), algorithms=["HS256"])


def get_user_id_from_token(token: str) -> str | None:
    """Safely extract user ID from token, returning None on any error."""
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except Exception:
        return None
