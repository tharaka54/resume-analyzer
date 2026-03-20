"""
app/models/user.py — User model (MongoDB)
Find or create users by Google OAuth ID.
"""

from datetime import datetime, timezone
from bson import ObjectId
from app.models.db import get_db


def find_user_by_google_id(google_id: str) -> dict | None:
    """Find a user by their Google OAuth Subject ID."""
    db = get_db()
    return db.users.find_one({"google_id": google_id})


def find_user_by_id(user_id: str) -> dict | None:
    """Find a user by their MongoDB ObjectId string."""
    try:
        db = get_db()
        return db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


def create_user(google_id: str, email: str, name: str, picture: str = "") -> dict:
    """
    Create a new user from Google OAuth data.

    Returns:
        The newly created user document with _id as string.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    user_doc = {
        "google_id": google_id,
        "email": email,
        "name": name,
        "picture": picture,
        "created_at": now,
        "last_login": now,
    }
    result = db.users.insert_one(user_doc)
    user_doc["_id"] = str(result.inserted_id)
    return user_doc


def upsert_user(google_id: str, email: str, name: str, picture: str = "") -> dict:
    """
    Find or create a user. Updates last_login on each login.

    Returns:
        User document with _id as string.
    """
    db = get_db()
    existing = find_user_by_google_id(google_id)

    if existing:
        db.users.update_one(
            {"google_id": google_id},
            {"$set": {"last_login": datetime.now(timezone.utc), "picture": picture, "name": name}},
        )
        existing["_id"] = str(existing["_id"])
        return existing

    return create_user(google_id, email, name, picture)
