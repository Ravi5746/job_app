import re
import difflib
from app.services.automation.agent.deterministic_fill import DETERMINISTIC_FIELD_MAP

STATIC_LOOKUP = {
    "your name": "full_name",
    "your legal name": "full_name",
    "legal name": "full_name",
    "first name": "first_name",
    "last name": "last_name",
    "email address": "email",
    "cell phone": "phone",
    "mobile phone": "phone",
    "contact number": "phone",
}

QUESTION_CATEGORIES = {
    r"gender|sex|race|ethnicity|veteran|disability|lgbtq|demographic": "eeo_question",
    r"authorized|visa|sponsorship|citizen|right to work|permit|green card": "screening_question",
    r"why.*work|interest|motivation|cover.?letter|tell.*about|statement|essay": "custom_question",
    r"salary|compensation|expected.?pay|ctc|remuneration": "screening_question",
    r"notice.?period|notice|availability|start.?date|when.?can.?you.?start": "screening_question",
    r"criminal|background|conviction|felony": "screening_question",
    r"how many|years of|experience with|proficiency|skilled": "screening_question",
    r"certif|license|clearance": "screening_question",
}

CANONICAL_FIELDS = [
    "first_name", "last_name", "full_name", "email", "phone", "location", 
    "city", "state_province", "postal_code", "country", "address_line_1", 
    "address_line_2", "linkedin_url", "github_url", "portfolio_url", 
    "current_company", "graduation_year", "degree_type", "expected_salary",
    "notice_period", "willing_to_relocate", "work_authorization"
]

def classify(label: str, name: str = "", field_id: str = "", placeholder: str = "", aria_label: str = "") -> str:
    res = _core_classify(label, name, field_id, placeholder, aria_label)
    
    # Strictly normalize: lowercase, strip outer spacing, clean out newlines/carriage returns
    res = res.lower().strip().replace("\n", "").replace("\r", "")
    
    # Semantic synonym mappings via difflib / direct matching
    synonyms = {
        "resume": ["resume", "cv", "履歴書/cv", "curriculum vitae", "resum"],
        "cover_letter": ["cover_letter", "cover letter", "coverletter"],
        "full_name": ["full_name", "fullname", "name", "your name"],
        "phone": ["phone", "téléphone", "mobile", "cell", "telephone"],
    }
    
    for canonical, variations in synonyms.items():
        if res in variations:
            return canonical
        for var in variations:
            if difflib.SequenceMatcher(None, res, var).ratio() >= 0.85:
                return canonical
                
    return res

def _core_classify(label: str, name: str = "", field_id: str = "", placeholder: str = "", aria_label: str = "") -> str:
    # Gather all text signals
    signals = [
        label or "",
        name or "",
        field_id or "",
        placeholder or "",
        aria_label or ""
    ]
    combined_text = " ".join(signals).lower().strip()
    
    fallback_name = label or name or placeholder or aria_label or field_id or "uncategorized"

    if not combined_text:
        return fallback_name

    # Layer 1: Regex via DETERMINISTIC_FIELD_MAP
    for regex_str, canonical in DETERMINISTIC_FIELD_MAP.items():
        if re.search(regex_str, combined_text, re.IGNORECASE):
            return canonical

    # Layer 2: Static lookup table (direct match)
    for lookup_str, canonical in STATIC_LOOKUP.items():
        if lookup_str in combined_text:
            return canonical

    # Layer 3: difflib fuzzy match against known profile keys
    best_match = None
    best_score = 0.0
    for target in CANONICAL_FIELDS:
        # Check against signals individually for closer fuzzy alignment
        for sig in signals:
            if not sig:
                continue
            score = difflib.SequenceMatcher(None, sig.lower().strip(), target.replace("_", " ")).ratio()
            if score > best_score:
                best_score = score
                best_match = target
    if best_score >= 0.85 and best_match:
        return best_match

    # Layer 4: Question category regex mapping
    for pattern, category in QUESTION_CATEGORIES.items():
        if re.search(pattern, combined_text, re.IGNORECASE):
            return category

    # Layer 5: Fallback to the original field name instead of 'uncategorized'
    return fallback_name
