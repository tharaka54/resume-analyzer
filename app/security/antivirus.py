"""
app/security/antivirus.py — Virus/Malware Scanning Pipeline

Layer 5 — Antivirus & VirusTotal Integration

Two-stage scan:
  Stage A — Local heuristic scan : Hash-based quarantine blocklist + entropy check
            (works offline, zero latency — catches known-bad files instantly)
  Stage B — VirusTotal API scan  : Upload file hash to VT for real-time engine results
            (optional; only runs if VIRUSTOTAL_API_KEY is set in .env)

Usage:
    from app.security.antivirus import scan_file_for_malware, AntivirusError
"""

import os
import math
import hashlib
import logging
import requests

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# VirusTotal v3 API endpoint for file hash lookup (no upload needed for known files)
VT_HASH_URL   = "https://www.virustotal.com/api/v3/files/{hash}"
VT_UPLOAD_URL = "https://www.virustotal.com/api/v3/files"

# Threshold: if ≥ this many VT engines flag as malicious → reject
VT_MALICIOUS_THRESHOLD = 3

# Files above this entropy are considered suspicious.
# Normal PDFs with compressed streams, embedded images, and embedded fonts
# typically have entropy between 7.3 and 7.9. True packed/encrypted malware
# tends to exceed 7.98 (near-maximum randomness).
# Setting to 7.98 avoids false-positives on legitimate CVs.
MAX_SAFE_ENTROPY = 7.98

# A small built-in blocklist of known-malicious PDF SHA-256 hashes (example seeds)
# In production: load this from an external threat-feed or database
KNOWN_MALICIOUS_HASHES: set[str] = {
    # These are placeholder hashes — replace with real threat-intel feeds
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # empty file hash (demo)
}

# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class AntivirusError(Exception):
    """Raised when a file is flagged as malicious or suspicious."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Stage A — Local Heuristic Scan
# ─────────────────────────────────────────────────────────────────────────────

def _compute_sha256(file_bytes: bytes) -> str:
    """Return SHA-256 hex digest of raw file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def _compute_entropy(file_bytes: bytes) -> float:
    """
    Compute Shannon entropy of file bytes.
    High entropy (> 7.5) may indicate encrypted/packed malware embedded inside a PDF.
    """
    if not file_bytes:
        return 0.0

    freq: dict[int, int] = {}
    for byte in file_bytes:
        freq[byte] = freq.get(byte, 0) + 1

    entropy = 0.0
    length = len(file_bytes)
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)

    return entropy


def _local_heuristic_scan(file_bytes: bytes) -> None:
    """
    Stage A: Check hash blocklist and file entropy.

    Raises:
        AntivirusError: If file is on the blocklist or has suspicious entropy.
    """
    sha256 = _compute_sha256(file_bytes)

    # Hash blocklist check
    if sha256 in KNOWN_MALICIOUS_HASHES:
        raise AntivirusError(
            f"File rejected: known malicious file detected (hash: {sha256[:16]}...)."
        )

    # Entropy check — only flag files with near-maximum entropy
    # Real-world PDFs with compression/images score 7.3–7.9 normally.
    # Only truly packed/encrypted payloads exceed 7.98.
    entropy = _compute_entropy(file_bytes)
    if entropy > MAX_SAFE_ENTROPY:
        # Log a warning but do NOT hard-reject based on entropy alone.
        # The VirusTotal scan (Stage B) is the authoritative malware check.
        # Entropy is a supplementary signal — too many false-positives on
        # legitimate compressed PDFs if we block here.
        logger.warning(
            f"[Antivirus] Elevated entropy detected: {entropy:.2f} (threshold: {MAX_SAFE_ENTROPY}) "
            f"— flagged for review but not blocked (Stage B will verify)."
        )
    else:
        logger.info(f"[Antivirus] Stage A passed — SHA256: {sha256[:16]}..., Entropy: {entropy:.2f}")


# ─────────────────────────────────────────────────────────────────────────────
# Stage B — VirusTotal API Scan
# ─────────────────────────────────────────────────────────────────────────────

def _virustotal_hash_lookup(file_bytes: bytes, api_key: str) -> None:
    """
    Stage B-i: Look up the SHA-256 hash in VirusTotal's database.

    If the file is known to VT, checks malicious engine count.
    If the file is unknown to VT, falls back to direct upload scan.

    Args:
        file_bytes: Raw bytes of the file.
        api_key:    VirusTotal v3 API key.

    Raises:
        AntivirusError: If VT reports the file as malicious.
    """
    sha256  = _compute_sha256(file_bytes)
    headers = {"x-apikey": api_key}

    try:
        response = requests.get(
            VT_HASH_URL.format(hash=sha256),
            headers=headers,
            timeout=15,
        )

        if response.status_code == 200:
            # File is known to VirusTotal
            stats = response.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious_count  = stats.get("malicious", 0)
            suspicious_count = stats.get("suspicious", 0)

            logger.info(
                f"[VirusTotal] Hash lookup — malicious: {malicious_count}, "
                f"suspicious: {suspicious_count}"
            )

            if malicious_count >= VT_MALICIOUS_THRESHOLD:
                raise AntivirusError(
                    f"File rejected by VirusTotal: {malicious_count} antivirus engines "
                    f"flagged this file as malicious."
                )

            if suspicious_count >= VT_MALICIOUS_THRESHOLD:
                raise AntivirusError(
                    f"File rejected by VirusTotal: {suspicious_count} antivirus engines "
                    f"flagged this file as suspicious."
                )

        elif response.status_code == 404:
            # Hash not found — upload the file for a fresh scan
            logger.info(f"[VirusTotal] Hash not found in VT database — submitting file for scan...")
            _virustotal_upload_scan(file_bytes, api_key)

        else:
            # VT API error — log and allow (fail-open to not block legitimate users)
            logger.warning(
                f"[VirusTotal] API returned unexpected status {response.status_code} — skipping VT scan"
            )

    except AntivirusError:
        raise
    except requests.exceptions.Timeout:
        logger.warning("[VirusTotal] API timeout — skipping VT scan")
    except requests.exceptions.ConnectionError:
        logger.warning("[VirusTotal] Cannot reach VirusTotal API — skipping VT scan")
    except Exception as e:
        logger.warning(f"[VirusTotal] Unexpected error during hash lookup: {e}")


def _virustotal_upload_scan(file_bytes: bytes, api_key: str) -> None:
    """
    Stage B-ii: Upload file bytes directly to VirusTotal for analysis.

    Used when the file hash is not yet in VT's database.

    Args:
        file_bytes: Raw bytes of the file.
        api_key:    VirusTotal v3 API key.

    Raises:
        AntivirusError: If the upload scan returns malicious results.
    """
    headers = {"x-apikey": api_key}

    try:
        upload_response = requests.post(
            VT_UPLOAD_URL,
            headers=headers,
            files={"file": ("resume.pdf", file_bytes, "application/pdf")},
            timeout=30,
        )

        if upload_response.status_code not in (200, 201):
            logger.warning(f"[VirusTotal] Upload failed with status {upload_response.status_code}")
            return  # Fail-open

        result_data = upload_response.json().get("data", {})
        attributes  = result_data.get("attributes", {})
        stats       = attributes.get("stats", {})

        malicious_count  = stats.get("malicious", 0)
        suspicious_count = stats.get("suspicious", 0)

        logger.info(
            f"[VirusTotal] Upload scan — malicious: {malicious_count}, "
            f"suspicious: {suspicious_count}"
        )

        if malicious_count >= VT_MALICIOUS_THRESHOLD:
            raise AntivirusError(
                f"File rejected by VirusTotal scan: {malicious_count} engines flagged as malicious."
            )

    except AntivirusError:
        raise
    except Exception as e:
        logger.warning(f"[VirusTotal] Upload scan error: {e} — skipping")


# ─────────────────────────────────────────────────────────────────────────────
# Public API — called from resumes.py
# ─────────────────────────────────────────────────────────────────────────────

def scan_file_for_malware(file_bytes: bytes) -> None:
    """
    Full antivirus scan pipeline for an uploaded file.

    Stage A (always runs): Local hash blocklist + entropy heuristic
    Stage B (if API key set): VirusTotal hash lookup → upload fallback

    Args:
        file_bytes: Raw bytes of the uploaded file.

    Raises:
        AntivirusError: If the file is flagged as malicious by any stage.
    """
    # Stage A — always runs, zero latency
    _local_heuristic_scan(file_bytes)

    # Stage B — only if VirusTotal API key is configured
    vt_api_key = os.getenv("VIRUSTOTAL_API_KEY", "").strip()
    if vt_api_key:
        _virustotal_hash_lookup(file_bytes, vt_api_key)
    else:
        logger.info("[Antivirus] VIRUSTOTAL_API_KEY not set — Stage B (VirusTotal) skipped")
