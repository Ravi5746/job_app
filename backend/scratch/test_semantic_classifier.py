import sys
import os
import numpy as np

# Adjust sys.path to include the backend directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.automation.agent.deterministic_fill import _resolve_profile_value
from app.services.automation.agent.semantic_classifier import semantic_classifier, HAS_SENTENCE_TRANSFORMERS

def test_resolve_profile_value():
    print("=== Testing Deterministic Resolve logic ===")
    mock_profile = {
        "full_name": "Ravi Kumar",
        "phone_country_code": "+91",
        "location": "Bangalore, India",
        "work_experience": [
            {"company": "Google", "role": "Senior Software Engineer"},
            {"company": "Meta", "role": "Software Engineer II"}
        ],
        "education": [
            {"degree": "Master of Science", "year": "2024", "field": "Computer Science"},
            {"degree": "Bachelor of Technology", "year": "2022", "field": "Information Technology"}
        ],
        "willing_to_relocate": True,
        "total_years_experience": 4
    }

    # Test Extended Fields
    print(f"current_company: expected='Google', got='{_resolve_profile_value(mock_profile, 'current_company')}'")
    print(f"current_title: expected='Senior Software Engineer', got='{_resolve_profile_value(mock_profile, 'current_title')}'")
    print(f"graduation_year: expected='2024', got='{_resolve_profile_value(mock_profile, 'graduation_year')}'")
    print(f"degree_type: expected='Master of Science', got='{_resolve_profile_value(mock_profile, 'degree_type')}'")
    print(f"employment_type: expected='Full-time', got='{_resolve_profile_value(mock_profile, 'employment_type')}'")
    print(f"willing_to_relocate: expected='Yes', got='{_resolve_profile_value(mock_profile, 'willing_to_relocate')}'")
    print(f"total_years_experience: expected='4', got='{_resolve_profile_value(mock_profile, 'total_years_experience')}'")

def test_semantic_classification():
    print("\n=== Testing Semantic Classification ===")
    if not HAS_SENTENCE_TRANSFORMERS:
        print("sentence-transformers is NOT installed/loaded. Skipping model classification test.")
        return

    # Check some test field labels
    test_labels = [
        "what company do you currently work at?",
        "graduation date",
        "highest qualification level",
        "desired job status",
        "expected compensation",
        "how many years have you been working?",
        "are you open to relocating?",
        "Current employer:",
        "Years of experience:",
        "Expected salary",
        "Notice period",
        "Willing to relocate?",
        "Highest Degree",
        "Job Type"
    ]

    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Access the raw classification logic without the threshold
    for label in test_labels:
        # We simulate the classify logic to print raw scores
        input_emb = semantic_classifier.model.encode([label], convert_to_numpy=True)
        norm = np.linalg.norm(input_emb, axis=1, keepdims=True)
        input_emb = input_emb / np.maximum(norm, 1e-12)
        
        best_category = None
        best_score = -1.0
        for category, embeddings in semantic_classifier.category_embeddings.items():
            similarities = np.dot(embeddings, input_emb.T).flatten()
            max_sim = float(np.max(similarities))
            if max_sim > best_score:
                best_score = max_sim
                best_category = category
                
        category, score = semantic_classifier.classify_field(label)
        print(f"Label: '{label}'\n  -> Raw Best Category: '{best_category}' (Score: {best_score:.4f})\n  -> Thresholded: '{category}' (Score: {score if score is not None else 0.0:.4f})")

if __name__ == "__main__":
    test_resolve_profile_value()
    test_semantic_classification()
