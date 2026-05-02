"""
app/security/input_sanitizer.py — Input Sanitization & NoSQL Injection Guard

Layer 4 — Text / JSON Sanitization
  • Strips dangerous HTML and script tags from all text inputs (XSS prevention)
  • Detects and blocks MongoDB operator injection ($where, $gt, $ne, etc.)
  • Enforces max-length limits per field type

Usage:
    from app.security.input_sanitizer import sanitize_text, guard_nosql, sanitize_job_payload
"""

import re
import bleach

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Bleach: no HTML tags allowed in any user text input
ALLOWED_TAGS: list = []
ALLOWED_ATTRS: dict = {}

# MongoDB operator pattern — catches $where, $gt, $ne, $regex, $or, etc.
NOSQL_OPERATOR_RE = re.compile(r'(\$[a-zA-Z]+)', re.IGNORECASE)

# Per-field max lengths (characters)
FIELD_MAX_LENGTHS: dict[str, int] = {
    "title":           200,
    "company":         150,
    "location":        150,
    "job_type":         50,
    "required_skills": 500,
    "description":    5000,
    "name":            150,
    "email":           254,   # RFC 5321
    "status":           50,
    "logo_url":       1000,
    "default":        1000,
}


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class InputSanitizationError(Exception):
    """Raised when a field contains dangerous or oversized content."""
    pass


class NoSQLInjectionError(Exception):
    """Raised when a MongoDB operator is detected in user input."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Core helpers
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_text(value: str, field_name: str = "field") -> str:
    """
    Strip all HTML tags and truncate to the allowed max length.

    Args:
        value:      Raw user-supplied string.
        field_name: Field label used in error messages.

    Returns:
        Cleaned, length-capped string.

    Raises:
        InputSanitizationError: If value exceeds allowed length after cleaning.
    """
    if not isinstance(value, str):
        return value  # Non-strings (numbers, booleans) pass through unchanged

    # Strip HTML / script tags via bleach
    cleaned = bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True).strip()

    # Enforce max length
    max_len = FIELD_MAX_LENGTHS.get(field_name, FIELD_MAX_LENGTHS["default"])
    if len(cleaned) > max_len:
        raise InputSanitizationError(
            f"Field '{field_name}' exceeds maximum allowed length of {max_len} characters."
        )

    return cleaned


def guard_nosql(data: dict) -> None:
    """
    Recursively scan a parsed JSON dict for MongoDB operator keys.

    Detects payloads like: {"email": {"$gt": ""}} or {"title": "$where: ..."}

    Args:
        data: The dictionary to inspect.

    Raises:
        NoSQLInjectionError: If any key or string value contains a $ operator.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            # Reject keys that are MongoDB operators
            if NOSQL_OPERATOR_RE.search(str(key)):
                raise NoSQLInjectionError(
                    f"NoSQL injection attempt detected: prohibited key '{key}'."
                )
            guard_nosql(value)

    elif isinstance(data, list):
        for item in data:
            guard_nosql(item)

    elif isinstance(data, str):
        if NOSQL_OPERATOR_RE.search(data):
            raise NoSQLInjectionError(
                f"NoSQL injection attempt detected in value: '{data[:80]}'"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Payload-level sanitizers (used directly in route handlers)
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_job_payload(data: dict) -> dict:
    """
    Sanitize and validate a job creation / update payload.

    Runs NoSQL injection guard first, then sanitizes each text field.

    Args:
        data: Raw parsed JSON from request.get_json().

    Returns:
        Dict with all string values cleaned.

    Raises:
        NoSQLInjectionError:     On MongoDB operator detection.
        InputSanitizationError:  On oversized or malformed fields.
    """
    guard_nosql(data)

    sanitized = {}
    text_fields = ["title", "description", "company", "location", "job_type", "required_skills", "logo_url"]

    for field in text_fields:
        if field in data:
            sanitized[field] = sanitize_text(str(data[field]), field_name=field)

    return sanitized


def sanitize_status_payload(data: dict) -> str:
    """
    Sanitize a status update payload and return the cleaned status string.

    Args:
        data: Raw parsed JSON from request.get_json().

    Returns:
        Cleaned status string.

    Raises:
        NoSQLInjectionError:    On MongoDB operator detection.
        InputSanitizationError: On oversized input.
    """
    guard_nosql(data)
    raw_status = data.get("status", "")
    return sanitize_text(str(raw_status), field_name="status")
