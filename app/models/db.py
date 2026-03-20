"""
app/models/db.py — Shared MongoDB client
Single PyMongo connection reused across all models.
"""

import os
from pymongo import MongoClient

_client: MongoClient | None = None
_db = None


def get_db():
    """Return the database instance (lazy singleton)."""
    global _client, _db
    if _db is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/resume_analyzer")
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        _db = _client.get_default_database()
    return _db
