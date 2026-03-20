"""
app/ai/skill_extractor.py — Dynamic spaCy-based Skill Extraction & Gap Analysis

Uses spaCy's NLP pipeline to dynamically extract noun phrases and named entities
without relying on a hardcoded vocabulary. This allows it to work for any industry.
"""

from functools import lru_cache
import re
from app.ai.preprocess import normalize_raw_text

@lru_cache(maxsize=1)
def _load_nlp():
    """Load spaCy model once and cache it."""
    try:
        import spacy
        try:
            return spacy.load("en_core_web_md")
        except OSError:
            return spacy.load("en_core_web_sm")
    except Exception as e:
        print(f"[spaCy] Model load error: {e}. Falling back to regex matching.")
        return None


# Words that commonly appear in JD boilerplate but are NOT actual skills.
# Any extracted term that contains one of these words will be discarded.
_BLOCKLIST = {
    "responsibilities", "responsibility", "requirement", "requirements",
    "qualification", "qualifications", "summary", "overview", "objective",
    "ideal", "candidate", "developer", "engineer", "manager", "specialist",
    "experience", "minimum", "years", "year", "job", "title", "role",
    "key", "core", "preferred", "strong", "proven", "demonstrated",
    "deep", "excellent", "exceptional", "good", "great", "high", "latest",
    "ability", "abilities", "understanding", "knowledge", "expertise",
    "background", "seeking", "looking", "opportunity", "opportunities",
    "team", "teams", "cross", "functional", "alignment", "transparency",
    "passion", "motivated", "self", "motivated", "improvement",
    "familiarity", "architectural", "modern", "scalable", "robust",
    "proficiency", "proficient", "skilled", "working", "including",
}


def _is_blocked(term: str) -> bool:
    """Return True if any word in the term is in the blocklist."""
    return any(word in _BLOCKLIST for word in term.lower().split())


def extract_skills(text: str) -> list[str]:
    """
    Dynamically extract key terms, noun phrases, and entities from text using spaCy.
    This replaces the hardcoded dictionary approach, allowing it to adapt to any industry.

    Returns:
        Deduplicated list of lowercase cleaned keyword strings found in text.
    """
    if not text:
        return []

    nlp = _load_nlp()
    found: set[str] = set()

    if nlp:
        # Normalise bullets/slashes BEFORE spaCy sees the text
        text = normalize_raw_text(text)
        # Limit to 100k chars for performance
        doc = nlp(text[:100_000])
        
        # 1. Extract Named Entities (Organizations, Products, Technical terms)
        for ent in doc.ents:
            # Filter out generic numbers, dates, times and money
            if ent.label_ not in ("CARDINAL", "DATE", "TIME", "PERCENT", "MONEY", "QUANTITY", "ORDINAL"):
                clean = ent.text.lower().strip()
                # remove punctuation at start and end
                clean = re.sub(r'^[^\w]+|[^\w]+$', '', clean)
                # Skip if empty, too short, more than 3 words, or a boilerplate JD phrase
                if len(clean) > 2 and len(clean.split()) <= 3 and not _is_blocked(clean):
                    found.add(clean)

        # 2. Extract Noun Chunks (Concepts, Processes, Frameworks)
        for chunk in doc.noun_chunks:
            # Filter out standalone pronouns
            if chunk.root.pos_ == "PRON":
                continue
                
            # Reconstruct the chunk without stopwords (like 'a', 'the', 'their')
            clean_words = []
            for token in chunk:
                # Keep significant words
                if not token.is_stop and not token.is_punct and len(token.text) > 1:
                    clean_words.append(token.text.lower())
            
            clean = " ".join(clean_words).strip()
            # Skip if empty, too short, more than 3 words, or a boilerplate JD phrase
            if len(clean) > 2 and len(clean.split()) <= 3 and not _is_blocked(clean):
                found.add(clean)

    else:
        # If spaCy fails to load, use a very basic regex fallback to find capitalized words or phrases
        # This is a last resort fallback layer
        matches = re.findall(r'\b[A-Z][a-z]+(?: \b[A-Z][a-z]+)*\b', text)
        for match in matches:
            if len(match) > 2:
                found.add(match.lower())

    return sorted(found)


def compute_skill_gap(
    jd_skills: list[str], cv_skills: list[str]
) -> tuple[list[str], list[str]]:
    """
    Compare dynamically extracted job description skills vs resume skills.

    Args:
        jd_skills: Dynamically extracted terms from the job description.
        cv_skills: Dynamically extracted terms from the candidate's resume.

    Returns:
        Tuple of (matched_skills, missing_skills).
    """
    matched = set()
    missing = set()
    
    cv_text_joined = " | ".join(cv_skills)
    
    for jd_term in jd_skills:
        # Direct exact match (e.g., CV literally says "revenue management")
        if jd_term in cv_skills:
            matched.add(jd_term)
        # Substring match (e.g., JD asks for "cpr", CV has "cpr certified")
        elif jd_term in cv_text_joined:
            matched.add(jd_term)
        else:
            missing.add(jd_term)

    return sorted(matched), sorted(missing)

