import os
import sys
import re

sys.path.append("d:/automation/Job Applied/backend")
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/automation/Job Applied/backend/.env", "r") as f:
    for line in f:
        if line.strip() and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ[k] = v

def get_words(sentence: str) -> set:
    return set(re.findall(r'\w+', sentence.lower()))

def calculate_jaccard_similarity(s1: str, s2: str) -> float:
    w1 = get_words(s1)
    w2 = get_words(s2)
    if not w1 or not w2:
        return 0.0
    return len(w1.intersection(w2)) / len(w1.union(w2))

BOILERPLATE_PATTERNS = [
    r"\bresponsible\s+for\b",
    r"\bworked\s+closely\s+with\b",
    r"\bcollaborated\s+with\b",
    r"\bparticipated\s+in\b",
    r"\bassisted\s+in\b",
    r"\bdaily\s+standups?\b",
    r"\bagile\s+ceremonies\b",
    r"\bsprint\s+planning\b",
    r"\bteam\s+meetings?\b",
    r"\bmeeting\s+project\s+deadlines\b",
    r"\bday-to-day\s+tasks?\b",
    r"\bgeneral\s+maintenance\b",
    r"\bdebugging\s+issues\b",
    r"\bfixing\s+bugs\b",
    r"\bwriting\s+clean\s+code\b",
    r"\bparticipating\s+in\b",
    r"\bpartnered\s+with\b",
    r"\bworking\s+in\s+short\s+iterations\b"
]

TECH_INDICATORS = [
    r"\b[A-Z][a-zA-Z0-9]*\b",
    r"\b\d+%\b",
    r"\b\d+\s*(?:years?|months?|days?|kb|mb|gb|tb|seconds?|ms)\b",
    r"\b(?:REST|API|SQL|NoSQL|CI/CD|AWS|GCP|UI|UX|JVM|JPA|MVC|RBAC|OAuth2?|LDAP|SAML)\b"
]

def is_generic_boilerplate(sentence: str) -> bool:
    clean_text = sentence.strip()
    if not clean_text:
        return True
    has_boilerplate = any(re.search(pat, clean_text, re.IGNORECASE) for pat in BOILERPLATE_PATTERNS)
    if not has_boilerplate:
        return False
    has_tech = any(re.search(pat, clean_text) for pat in TECH_INDICATORS)
    has_numbers = any(char.isdigit() for char in clean_text)
    return has_boilerplate and not (has_tech or has_numbers)

def main():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.ai.compressor import ResumeCompressor

    db_url = os.environ.get("DATABASE_URL")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    from sqlalchemy import text
    result = db.execute(text("SELECT content FROM resumes ORDER BY id DESC LIMIT 1")).fetchone()
    resume_content = result[0]
    
    print(f"Original length: {len(resume_content)}")
    
    compressed_text = ResumeCompressor.compress_resume(resume_content)
    
    print(f"Compressed length: {len(compressed_text)}")
    print(f"Reduction Ratio: {len(compressed_text) / len(resume_content):.2%}")
    print(f"Compression Percentage: {100.0 - (len(compressed_text) / len(resume_content) * 100.0):.2f}% reduced")
    
    print("\n--- SAMPLE OF COMPRESSED RESUME ---")
    print(compressed_text[:1200])
    print("\n--- END OF SAMPLE ---")
    
    db.close()

if __name__ == "__main__":
    main()
