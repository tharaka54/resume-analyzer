"""
app/ai/preprocess.py — Text Cleaning, Tokenization, Stopword Removal
"""

import re
import string
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

# Download NLTK data on first import
for resource in ["stopwords", "punkt", "wordnet", "punkt_tab"]:
    try:
        nltk.data.find(f"tokenizers/{resource}" if resource.startswith("punkt") else f"corpora/{resource}")
    except Exception:
        nltk.download(resource, quiet=True)

_STOP_WORDS = set(stopwords.words("english"))
_LEMMATIZER = WordNetLemmatizer()

# Extra noise patterns common in resumes
_NOISE_PATTERNS = [
    r"http\S+",                     # URLs
    r"\S+@\S+",                     # Emails
    r"\+?[\d\s\-\(\)]{7,}",        # Phone numbers
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b",  # Months
    r"\b\d{4}\b",                   # Years (optional — comment out if needed)
    r"[^\x00-\x7F]+",              # Non-ASCII
]

# Bullet/list characters that PDFs inject into text
_BULLET_CHARS = re.compile(r"[\u2022\u00b7\u25aa\u25b8\u25e6\u2023\u27a2\u27a4\u25ba\u2013\u2014]+")


def normalize_raw_text(text: str) -> str:
    """
    Light normalisation applied BEFORE spaCy / skill extraction.
    Removes PDF bullet characters and normalises separators so they
    don't bleed into skill names (e.g. 'kubernetes \u2022 aws', 'ci/cd').
    """
    if not text:
        return text
    # Replace bullet characters with a space
    text = _BULLET_CHARS.sub(" ", text)
    # Normalise slashes used as separators (CI/CD -> CI CD, AWS/GCP -> AWS GCP)
    text = re.sub(r"\s*/\s*", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"  +", " ", text)
    return text


def clean_text(text: str) -> str:
    """Full preprocessing pipeline: lowercase → noise removal → punctuation → stopwords → lemmatize."""
    if not isinstance(text, str):
        return ""

    # Lowercase
    text = text.lower()

    # Remove noise patterns
    for pattern in _NOISE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    # Remove punctuation
    text = text.translate(str.maketrans(string.punctuation, " " * len(string.punctuation)))

    # Tokenize
    tokens = word_tokenize(text)

    # Remove stopwords + short tokens + lemmatize
    tokens = [
        _LEMMATIZER.lemmatize(tok)
        for tok in tokens
        if tok.isalpha() and tok not in _STOP_WORDS and len(tok) > 2
    ]

    return " ".join(tokens)


def extract_keywords(text: str) -> list[str]:
    """Return cleaned token list from text."""
    cleaned = clean_text(text)
    return cleaned.split()


def tokenize_sentences(text: str) -> list[str]:
    """Split raw text into individual sentences."""
    try:
        from nltk.tokenize import sent_tokenize
        return sent_tokenize(text)
    except Exception:
        return [s.strip() for s in text.split(".") if s.strip()]
