import os
import sys
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

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
    db_url = os.environ.get("DATABASE_URL")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    result = db.execute(text("SELECT content FROM resumes ORDER BY id DESC LIMIT 1")).fetchone()
    resume_content = result[0]
    
    print(f"Total Resume length: {len(resume_content)}")
    
    lines = resume_content.splitlines()
    print(f"Total raw lines: {len(lines)}")
    
    # Reconstruct
    reconstructed = []
    current = ""
    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue
        is_bullet = trimmed.startswith(("•", "-", "*", "▪", "◦"))
        is_header = len(trimmed) < 40 and (trimmed.isupper() or trimmed.endswith(":"))
        is_structural = len(trimmed) < 80 and trimmed[0].isupper() and any(x in trimmed for x in ["Client:", "Role:", "Responsibilities", "Aug", "Present", "202"])
        
        if is_bullet or is_header or is_structural:
            if current:
                reconstructed.append(current)
            current = trimmed
        else:
            if current:
                current += " " + trimmed
            else:
                current = trimmed
    if current:
        reconstructed.append(current)
        
    print(f"Total reconstructed blocks: {len(reconstructed)}")
    
    bullets = [b for b in reconstructed if b.startswith(("•", "-", "*", "▪", "◦"))]
    print(f"Total bullets: {len(bullets)}")
    
    # Check Jaccard similarities between bullets
    high_sim = []
    for i in range(len(bullets)):
        for j in range(i+1, len(bullets)):
            sim = calculate_jaccard_similarity(bullets[i], bullets[j])
            if sim > 0.4:
                high_sim.append((i, j, sim, bullets[i], bullets[j]))
                
    high_sim.sort(key=lambda x: x[2], reverse=True)
    print(f"Pairs with similarity > 0.4: {len(high_sim)}")
    print("--- TOP 5 SIMILAR PAIRS (FULL) ---")
    for idx, (i, j, sim, b1, b2) in enumerate(high_sim[:5]):
        print(f"\nPair {idx+1}: Similarity {sim:.4f}")
        print(f"  Bullet {i}: {repr(b1)}")
        print(f"  Bullet {j}: {repr(b2)}")
        w1 = get_words(b1)
        w2 = get_words(b2)
        print(f"  Words in B1: {w1}")
        print(f"  Words in B2: {w2}")
        print(f"  Intersection: {w1.intersection(w2)}")
        print(f"  Difference B1-B2: {w1 - w2}")
        print(f"  Difference B2-B1: {w2 - w1}")
        
    # Check boilerplate filtering on sample bullets
    print("\n--- BOILERPLATE CHECK SAMPLES ---")
    boilerplate_candidates = [
        "• Practiced Agile methodologies (Scrum/Kanban), participating in sprint planning, backlog grooming and daily stand-ups; used JIRA, Bitbucket and Confluence for task tracking.",
        "• Participated in daily standups and sprint planning.",
        "• Worked closely with cross-functional teams to deliver projects on time."
    ]
    for bc in boilerplate_candidates:
        clean_text = bc.strip()
        has_boilerplate = any(re.search(pat, clean_text, re.IGNORECASE) for pat in BOILERPLATE_PATTERNS)
        has_tech = any(re.search(pat, clean_text) for pat in TECH_INDICATORS)
        has_numbers = any(char.isdigit() for char in clean_text)
        print(f"\nText: {repr(bc)}")
        print(f"  has_boilerplate: {has_boilerplate}")
        print(f"  has_tech (broad): {has_tech}")
        # Find which tech indicator pattern matched
        for pat in TECH_INDICATORS:
            m = re.search(pat, clean_text)
            if m:
                print(f"    Matched tech pattern: {pat} -> {repr(m.group(0))}")
        print(f"  has_numbers: {has_numbers}")
        print(f"  is_generic_boilerplate: {has_boilerplate and not (has_tech or has_numbers)}")

    db.close()

if __name__ == "__main__":
    main()
