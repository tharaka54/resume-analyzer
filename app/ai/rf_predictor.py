import os
import pickle
import pandas as pd

# Look for the copied brain file in the main project folder
MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
    "trained_models", 
    "random_forest_v1.pkl"
)

def predict_hiring_outcome(tfidf_score: float, bert_score: float, skills_matched: int) -> tuple[str, float]:
    """
    Dynamically loads the Random Forest model and predicts if the candidate will be hired.
    Returns: (Prediction "HIRED"/"REJECTED", Probability percentage)
    """
    if not os.path.exists(MODEL_PATH):
        # Graceful fallback logic if the ML brain is missing
        prob = (tfidf_score * 0.3) + (bert_score * 0.6) + (min(skills_matched, 15) / 15 * 0.1)
        hired = "HIRED" if prob > 0.65 else "REJECTED"
        return hired, min(100.0, prob * 100)

    try:
        with open(MODEL_PATH, 'rb') as f:
            model = pickle.load(f)
            
        candidate_df = pd.DataFrame([{
            'tfidf_score': tfidf_score,
            'bert_score': bert_score,
            'skills_matched': skills_matched
        }])
        
        prediction = model.predict(candidate_df)[0]
        # predict_proba returns array like [prob_rejected, prob_hired]
        probability = model.predict_proba(candidate_df)[0][1] * 100
        
        if prediction == 1:
            return "HIRED", float(probability)
        else:
            return "REJECTED", float(probability)
            
    except Exception as e:
        print(f"[ML Engine Error] {e}")
        return "UNKNOWN ERROR", 0.0
