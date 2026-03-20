import os
import json
import google.generativeai as genai

def generate_quiz_for_job(job_title: str, job_description: str, required_skills: str) -> list:
    """
    Generate a 20-question MCQ quiz based on the job description.
    Uses Google Gemini. Returns a list of dictionaries.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key == "your-gemini-api-key":
        return _fallback_quiz()

    genai.configure(api_key=api_key)

    prompt = f"""You are an expert technical recruiter and assessor.
Generate a 20-question multiple-choice quiz based on the following job requirements.

Job Title: {job_title}
Required Skills: {required_skills}
Description:
{job_description[:1500]}

Rules for the Quiz:
1. Provide exactly 20 questions.
2. Each question must have exactly 4 options.
3. Indicate the correct answer using the ZERO-BASED index (0, 1, 2, or 3) of the correct option.
4. The output MUST be a valid JSON array of objects. NO Markdown formatting, just pure JSON.

Example format:
[
  {{
    "question": "What is the primary purpose of React?",
    "options": ["To build databases", "To build user interfaces", "To manage servers", "To create CSS"],
    "correct_index": 1
  }}
]
"""
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        content = response.text.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        quiz_data = json.loads(content)
        if len(quiz_data) > 0:
            return quiz_data[:20]
        return _fallback_quiz()
    except Exception as e:
        print(f"[LLM Quiz Error] {e}")
        return _fallback_quiz()

def _fallback_quiz() -> list:
    """Rule-based fallback quiz of 20 basic questions."""
    q = {
        "question": "What is a core competency required for this role?",
        "options": ["Hard Work", "Punctuality", "Technical Skills", "All of the above"],
        "correct_index": 3
    }
    return [q for _ in range(20)]
