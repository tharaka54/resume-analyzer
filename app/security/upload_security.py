"""
app/security/upload_security.py — Unified Upload Security Pipeline

All four upload security layers merged into a single module:

  Layer 1 — File Validator    : Extension, MIME type, file size checks
  Layer 2a— Magic Bytes       : Binary PDF header verification (%PDF-)
  Layer 2b— PDF Inspector     : Deep structural scan via PyMuPDF
  Layer 3 — Filename Sanitizer: UUID-based filename + path traversal guard
"""

import os
import re
import uuid
import fitz           # PyMuPDF
from flask import Request
from werkzeug.datastructures import FileStorage

# python-magic reads actual file bytes for MIME detection (FIX-07 / Tools table compliance)
# python-magic-bin ships the libmagic DLL for Windows.
# Wrapped in try/except so a missing DLL doesn't crash the server — Layer 1b falls back to
# the Content-Type header check in that case (same behaviour as pre-FIX-07).
try:
    import magic as _magic
    _MAGIC_AVAILABLE = True
except (ImportError, OSError):
    _MAGIC_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1 — File Validator
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS   = {"pdf"}
ALLOWED_MIME_TYPES   = {"application/pdf", "application/x-pdf"}
MAX_FILE_SIZE_BYTES  = 5 * 1024 * 1024   # 5 MB


class FileValidationError(Exception):
    """Raised when a file fails extension, MIME, or size validation."""
    pass


def validate_upload(file: FileStorage) -> None:
    """
    Layer 1: Validate extension, MIME type (via python-magic), and file size.

    Uses python-magic to read the actual file content bytes for MIME detection
    rather than trusting the browser-supplied Content-Type header.
    This prevents bypasses such as: rename malware.exe → resume.pdf and
    set Content-Type: application/pdf in the request.

    Args:
        file: Werkzeug FileStorage object from Flask request.files.

    Raises:
        FileValidationError: With a descriptive message on any violation.
    """
    if file is None or file.filename == "":
        raise FileValidationError("No file selected.")

    # 1a. Extension check
    ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"File type '.{ext}' is not allowed. Only PDF files are accepted."
        )

    # 1b. MIME type via python-magic (reads actual bytes, not browser header)
    #     This is more secure than trusting file.content_type which is caller-supplied.
    if _MAGIC_AVAILABLE:
        try:
            header_sample = file.stream.read(1024)   # Read first 1 KB for magic detection
            file.stream.seek(0)                       # Reset stream for subsequent reads
            detected_mime = _magic.from_buffer(header_sample, mime=True)
            if detected_mime not in ALLOWED_MIME_TYPES:
                raise FileValidationError(
                    f"File content detected as '{detected_mime}' — expected 'application/pdf'. "
                    f"The file content does not match its extension."
                )
        except FileValidationError:
            raise
        except Exception:
            # Magic check failed unexpectedly — fall back to header check below
            if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
                raise FileValidationError(
                    f"Invalid MIME type '{file.content_type}'. Expected 'application/pdf'."
                )
    else:
        # Fallback: trust Content-Type header (libmagic DLL unavailable on this system)
        if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
            raise FileValidationError(
                f"Invalid MIME type '{file.content_type}'. Expected 'application/pdf'."
            )

    # 1c. File size check
    file.stream.seek(0, 2)          # Seek to end
    size = file.stream.tell()
    file.stream.seek(0)             # Reset to start

    if size == 0:
        raise FileValidationError("Uploaded file is empty.")

    if size > MAX_FILE_SIZE_BYTES:
        max_mb    = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        actual_mb = size / (1024 * 1024)
        raise FileValidationError(
            f"File too large ({actual_mb:.2f} MB). Maximum allowed size is {max_mb:.0f} MB."
        )


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2a — Magic Bytes Checker
# ─────────────────────────────────────────────────────────────────────────────

PDF_MAGIC_BYTES  = b"%PDF-"
MAGIC_READ_LEN   = 5


class MagicBytesError(Exception):
    """Raised when a file's binary header does not match a valid PDF."""
    pass


def verify_pdf_magic_bytes(file_bytes: bytes) -> None:
    """
    Layer 2a: Confirm the first 5 bytes are the PDF magic signature.

    Catches renamed files (e.g. malware.exe → resume.pdf) that pass
    extension and MIME checks but are not real PDFs.

    Args:
        file_bytes: Raw bytes of the uploaded file.

    Raises:
        MagicBytesError: If the magic bytes don't match %PDF-.
    """
    if len(file_bytes) < MAGIC_READ_LEN:
        raise MagicBytesError("File is too small to be a valid PDF.")

    header = file_bytes[:MAGIC_READ_LEN]
    if header != PDF_MAGIC_BYTES:
        hex_repr = header.hex().upper()
        raise MagicBytesError(
            f"File does not have a valid PDF header. "
            f"Expected '%PDF-', got bytes: {hex_repr}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2b — PDF Deep Inspector
# ─────────────────────────────────────────────────────────────────────────────

# Keys that always trigger a hard reject
BLOCK_KEYS = {
    "/JS", "/JavaScript",   # Embedded JavaScript
    "/Launch",              # Launch actions (run executables)
    "/EmbeddedFile",        # Embedded file attachments
    "/OpenAction",          # Auto-run on open
    "/RichMedia",           # Flash/multimedia
    "/XFA",                 # XML Form Architecture
}


class PDFInspectionError(Exception):
    """Raised when a PDF fails structural security inspection."""
    pass


def inspect_pdf(file_bytes: bytes) -> str:
    """
    Layer 2b: Open the PDF with PyMuPDF and perform a deep structural scan.

    Checks:
      - File can be opened as a valid PDF
      - No embedded JavaScript, launch actions, or executables
      - Has at least one readable page with extractable text

    Args:
        file_bytes: Raw bytes of the uploaded PDF.

    Returns:
        Extracted plain text from the PDF (used downstream by NLP models).

    Raises:
        PDFInspectionError: If the PDF is malformed or contains dangerous content.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except fitz.FileDataError as e:
        raise PDFInspectionError(f"Cannot open file as a valid PDF: {e}")
    except Exception as e:
        raise PDFInspectionError(f"PDF parsing failed: {e}")

    if doc.page_count == 0:
        raise PDFInspectionError("PDF has no pages and cannot be processed.")

    # Scan PDF object tree for dangerous keys
    try:
        pdf_str = doc.tobytes().decode("latin-1", errors="ignore")
        for key in BLOCK_KEYS:
            if key in pdf_str:
                doc.close()
                raise PDFInspectionError(
                    f"Security violation: PDF contains prohibited element '{key}'. "
                    f"This file has been rejected."
                )
    except PDFInspectionError:
        raise
    except Exception:
        pass  # tobytes() may fail on some PDFs; proceed with text extraction

    # Extract text from all pages
    text_parts = []
    for page_num in range(doc.page_count):
        try:
            page = doc.load_page(page_num)
            text_parts.append(page.get_text("text"))
        except Exception:
            continue

    doc.close()

    extracted_text = "\n".join(text_parts).strip()

    if not extracted_text:
        raise PDFInspectionError(
            "PDF appears to contain only images or scanned content — "
            "text extraction failed. Please upload a text-based PDF."
        )

    return extracted_text


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 3 — Filename Sanitizer
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_filename(original_filename: str) -> str:
    """
    Layer 3: Discard the original filename and return a UUID4-based name.

    The original filename is stored in MongoDB metadata — never written to disk.
    This prevents path traversal attacks and filename injection.

    Args:
        original_filename: The user-supplied filename (untrusted input).

    Returns:
        A safe, unique filename such as '3f2a1e9c-....pdf'.
    """
    return f"{uuid.uuid4()}.pdf"


def get_safe_filepath(upload_folder: str, safe_filename: str) -> str:
    """
    Build an absolute path within the upload folder.

    Uses os.path.abspath to prevent directory traversal.

    Args:
        upload_folder: Base upload directory path.
        safe_filename: UUID-based filename from sanitize_filename().

    Returns:
        Absolute file path string, guaranteed to be inside upload_folder.

    Raises:
        ValueError: If the resolved path escapes the upload folder.
    """
    os.makedirs(upload_folder, exist_ok=True)
    abs_folder = os.path.abspath(upload_folder)
    filepath   = os.path.join(abs_folder, safe_filename)

    if not filepath.startswith(abs_folder):
        raise ValueError("Path traversal detected — aborting file save.")

    return filepath
