"""
app/ai/llm_explainer.py — Google Gemini API Plain-English Explanation Generator

Calls Google's free Gemini 1.5 Flash API to produce a recruiter-friendly, actionable summary
for each ranked resume, explaining WHY it scored as it did.
"""

import os
import google.generativeai as genai
from flask import current_app


def generate_explanation(
    candidate_name: str,
    job_title: str,
    job_description: str,
    resume_text: str,
    hybrid_score: float,
    matched_skills: list[str],
    missing_skills: list[str],
) -> str:
    """
    Ask Google Gemini to explain the resume score in plain English.

    Args:
        candidate_name: Name of the applicant.
        job_title:      Title of the job being applied for.
        job_description: Full text of the job posting.
        resume_text:    Extracted text from the candidate's PDF.
        hybrid_score:   Final score (0-100).
        matched_skills: Skills the candidate has.
        missing_skills: Skills the candidate is missing.

    Returns:
        Plain-English explanation string (2-3 paragraphs).
        On API failure, returns a graceful fallback message.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key == "your-gemini-api-key":
        return _fallback_explanation(
            candidate_name, hybrid_score, matched_skills, missing_skills
        )

    # Configure Gemini with the API key
    genai.configure(api_key=api_key)

    matched_str = ", ".join(matched_skills) if matched_skills else "None identified"
    missing_str = ", ".join(missing_skills) if missing_skills else "None — strong match!"

    prompt = f"""You are an expert HR recruitment assistant. A resume has been scored against a job posting using AI.

Job Title: {job_title}

Job Description (excerpt):
{job_description[:1500]}

Candidate Name: {candidate_name}

Resume Content (excerpt):
{resume_text[:2000]}

AI Scoring Results:
- Overall Score: {hybrid_score:.1f}/100
- Matched Skills: {matched_str}
- Missing Skills: {missing_str}

Please write a concise, professional 2-3 paragraph explanation for a recruiter covering:
1. Why this candidate scored {hybrid_score:.1f}/100 — what they do well
2. Key strengths relevant to this role
3. Specific skill gaps and whether they are critical or learnable

Be honest, actionable, and avoid generic statements. Address the candidate by name."""

    try:
        # Using Gemini 2.5 Flash: It is incredibly fast and free
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        
        return response.text.strip()

    except Exception as e:
        print(f"[LLM] Unexpected error with Gemini: {e}")
        return _fallback_explanation(candidate_name, hybrid_score, matched_skills, missing_skills)


def _fallback_explanation(
    name: str, score: float, matched: list[str], missing: list[str]
) -> str:
    """Rule-based fallback when Gemini API is unavailable or key is missing."""
    grade = (
        "excellent" if score >= 80
        else "good" if score >= 65
        else "moderate" if score >= 45
        else "low"
    )
    matched_str = ", ".join(matched[:5]) + ("..." if len(matched) > 5 else "") if matched else "none detected"
    missing_str = ", ".join(missing[:5]) + ("..." if len(missing) > 5 else "") if missing else "none — strong match"

    return (
        f"{name} achieved a {grade} match score of {score:.1f}/100. "
        f"Key matched skills include: {matched_str}. "
        f"Skills to address: {missing_str}. "
        f"{'This candidate appears well-suited for the role.' if score >= 65 else 'Further review recommended before advancing this candidate.'}"
    )

