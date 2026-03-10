import re
from typing import Optional

def clean_text(text: str) -> set:
    """Preprocess text by lowercasing, removing punctuation, and splitting into a set of words."""
    if not text:
        return set()
    # Remove non-alphanumeric characters and split
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
    # Basic stop words to ignore
    stop_words = {'and', 'the', 'to', 'of', 'in', 'for', 'with', 'a', 'on', 'is', 'as', 'at', 'an', 'by', 'be', 'this', 'that', 'from', 'or', 'are'}
    return set(w for w in words if w not in stop_words and len(w) > 2)

def calculate_cv_match(cv_text: str, job_text: str) -> int:
    """
    Calculates a basic match score (0-100) between a CV and a Job Description
    based on word/skill overlap.
    """
    if not cv_text or not job_text:
        return 0
        
    cv_words = clean_text(cv_text)
    job_words = clean_text(job_text)
    
    if not job_words or not cv_words:
        return 0
        
    # Find intersection
    common_words = cv_words.intersection(job_words)
    
    # We score based on how much of the job's key vocabulary (up to a limit) is in the CV.
    # To prevent extremely long JDs from unfairly lowering the score, we cap the denominator.
    # We assume a typical JD has about 50-100 meaningful keywords.
    denominator = min(len(job_words), 50) 
    
    # Calculate percentage
    score = (len(common_words) / denominator) * 100
    
    # Cap at 99 so it feels authentic, unless it's a perfect literal match
    return min(int(score), 99)

def get_job_relevancy_score(cv_text: Optional[str], job: dict) -> int:
    """Extracts text from a job dictionary and scores it against the CV."""
    if not cv_text:
        return 0
        
    # Combine relevant job fields for scoring
    jd_parts = [
        job.get("title", ""),
        job.get("tagsAndSkills", ""),
        job.get("jobDescription", ""),
        job.get("shortDescription", ""),
        job.get("fullDescription", "")
    ]
    
    job_full_text = " ".join(filter(None, jd_parts))
    return calculate_cv_match(cv_text, job_full_text)
