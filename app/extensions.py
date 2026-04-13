"""
app/extensions.py — Shared Flask Extension Instances

Centralises Flask-Limiter so all route blueprints can import
a single shared instance without circular imports.

Rate limits enforced per-route (NFR #9):
  /auth/login        → 3 per minute per IP
  /auth/callback     → 3 per minute per IP
  /quiz/*/start      → 5 per minute per IP
  /quiz/*/submit     → 5 per minute per IP
  /jobs/ POST        → 10 per hour per user
  /resumes upload    → 5 per hour per user
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],          # No blanket default — every limit is explicit
    storage_uri="memory://",    # In-process memory store (swap for Redis in prod)
)
