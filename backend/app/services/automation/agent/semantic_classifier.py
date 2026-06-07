import logging

logger = logging.getLogger(__name__)

# Try to import sentence_transformers and numpy
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    logger.warning("sentence-transformers or numpy is not installed. Semantic classification will be disabled.")

# Define standard categories and their representative labels
CATEGORIES = {
    "first_name": ["First Name", "Given Name", "First name"],
    "last_name": ["Last Name", "Surname", "Family Name", "Last name"],
    "full_name": ["Full Name", "Name", "Your name", "Complete name"],
    "email": ["Email", "Email address", "E-mail", "E-mail address"],
    "phone": ["Phone", "Phone number", "Mobile", "Mobile number", "Contact number", "Telephone"],
    "phone_country_code": ["Phone country code", "Country code", "Dial code", "Calling code", "Prefix"],
    "location": ["Location", "City", "Current location", "Where do you live", "Address"],
    "linkedin_url": ["LinkedIn", "LinkedIn URL", "LinkedIn profile", "LinkedIn page"],
    "github_url": ["GitHub", "GitHub URL", "GitHub profile", "GitHub page"],
    "portfolio_url": ["Portfolio", "Portfolio URL", "Website", "Personal website", "Personal page"],
    "current_company": ["Current company", "Present company", "Employer", "Current employer", "Present employer", "Company name"],
    "current_title": ["Current role", "Current title", "Current position", "Present title", "Present position", "Job title"],
    "graduation_year": ["Graduation year", "Year of graduation", "Year completed", "Completion year", "Education graduation year"],
    "degree_type": ["Degree type", "Degree", "Highest degree", "Education degree", "Degree level", "Highest level of education", "Qualification"],
    "employment_type": ["Employment type", "Job type", "Work type", "Desired employment", "Desired job type"],
    "expected_salary": ["Expected salary", "Target salary", "Desired salary", "Salary expectations"],
    "notice_period": ["Notice period", "Availability", "How soon can you start", "Notice"],
    "work_authorization": ["Work authorization", "Are you authorized to work", "Visa status", "Work permit"],
    "willing_to_relocate": ["Willing to relocate", "Are you willing to relocate", "Relocation"],
    "total_years_experience": ["Years of experience", "Experience level", "Work experience in years", "Total years of experience"]
}

class SemanticFieldClassifier:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.enabled = HAS_SENTENCE_TRANSFORMERS
        self.model = None
        self.category_embeddings = {}

        if self.enabled:
            try:
                logger.info(f"Loading SentenceTransformer model '{model_name}'...")
                self.model = SentenceTransformer(model_name)
                logger.info("SentenceTransformer model loaded successfully. Precomputing embeddings...")
                # Precompute embeddings for all category representatives
                for category, sentences in CATEGORIES.items():
                    embeddings = self.model.encode(sentences, convert_to_numpy=True)
                    # Normalize embeddings for easy cosine similarity
                    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                    self.category_embeddings[category] = embeddings / np.maximum(norms, 1e-12)
                logger.info("Category embeddings precomputed and normalized.")
            except Exception as e:
                logger.warning(f"Failed to initialize SemanticFieldClassifier: {e}. Disabling Layer 2.")
                self.enabled = False

    def classify_field(self, label: str) -> tuple[str, float] | tuple[None, None]:
        """
        Embeds the input label and compares cosine similarity against known categories.
        Returns (category, similarity_score) if similarity > 0.85, else (None, None).
        """
        if not self.enabled or not label or not label.strip():
            return None, None

        try:
            # Clean label
            clean_label = label.strip()
            # Encode and normalize input label
            input_emb = self.model.encode([clean_label], convert_to_numpy=True)
            norm = np.linalg.norm(input_emb, axis=1, keepdims=True)
            input_emb = input_emb / np.maximum(norm, 1e-12)  # shape (1, dim)

            best_category = None
            best_score = -1.0

            # Compute similarities against pre-normalized embeddings
            for category, embeddings in self.category_embeddings.items():
                # embeddings is (num_sentences, dim). Dot product with input_emb (1, dim) -> (num_sentences, 1)
                similarities = np.dot(embeddings, input_emb.T).flatten()
                max_sim = float(np.max(similarities))
                if max_sim > best_score:
                    best_score = max_sim
                    best_category = category

            logger.info(f"[SemanticClassifier] Field '{clean_label}' matched category '{best_category}' with score {best_score:.4f}")
            if best_score > 0.85:
                return best_category, best_score
        except Exception as e:
            logger.warning(f"Error during semantic field classification: {e}")

        return None, None


# Singleton instance
semantic_classifier = SemanticFieldClassifier()
