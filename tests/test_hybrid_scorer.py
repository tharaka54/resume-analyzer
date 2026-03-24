import pytest
import sys
import os

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ai.hybrid_scorer import score_resume, TFIDF_WEIGHT, BERT_WEIGHT, QUIZ_WEIGHT

def test_hybrid_scorer_combined_weights():
    """
    Test that the hybrid score correctly merges TF-IDF, BERT, and Quiz.
    Because BERT and TF-IDF actually rely on scikit-learn models, we will mock their functions
    or provide extremely basic texts to guarantee specific math results.
    """
    # 1. Provide an exact 1:1 match for job description and resume
    job_desc = "Python Flask MongoDB Developer"
    resume = "Python Flask MongoDB Developer"
    
    # 2. Assume 100% quiz score passes
    quiz_score = 1.0 
    
    # Run the real scorer
    result = score_resume(job_desc, resume, quiz_score=quiz_score)
    
    # If the text is identical, TF-IDF and BERT should theoretically return near 1.0.
    # Therefore, (1.0 * QUIZ_WEIGHT) + (1.0 * TFIDF_WEIGHT) + (1.0 * BERT_WEIGHT) should equal near 1.0 (or 100%).
    # We allow a very small tolerance since ML cosine similarity floats aren't always exactly 1.0000.
    assert result.hybrid_score > 0.90, f"Expected near 1.0 hybrid score, got {result.hybrid_score}"
    assert result.quiz_score == 1.0
    
def test_skill_gap_extraction():
    """Test that NER extraction detects missing skills properly."""
    job_desc = "Need React, Node and AWS experience."
    resume = "I am a Web Developer with React."
    
    result = score_resume(job_desc, resume, quiz_score=0.0)
    
    # The extraction should recognize React, Node, AWS as required.
    # The resume only has React.
    assert len(result.missing_skills) > 0, "Missing skills (Node, AWS) should have been registered."
    
def test_hybrid_score_low_math():
    """Test that completely unrelated CVs drop the score appropriately."""
    job_desc = "Java Enterprise Edition Backend Architect"
    resume = "Graphic Designer with Adobe Illustrator skills"
    quiz_score = 0.0
    
    result = score_resume(job_desc, resume, quiz_score=quiz_score)
    
    # If the content is fundamentally different, BERT and TF-IDF will crash drastically.
    # 0% quiz + low text match should result in an extremely low score.
    assert result.hybrid_score < 0.50, f"Expected low score for bad CV, got {result.hybrid_score}"
