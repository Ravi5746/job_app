import re
from app.core.logger import logger

DETERMINISTIC_FIELD_MAP = {
    # English + common i18n patterns
    r"country.?code|dial.?code|calling.?code|prefix|phone.*country|country.*phone": "phone_country_code",
    r"phone|mobile|telefon|téléphone|telefono|celular": "phone",
    r"\bcountry\b|\bpais\b|\bpays\b|\bland\b": "country",
    r"email|e-mail|correo|courriel": "email",
    r"first.?name|given.?name|prénom|nombre|vorname": "first_name",
    r"last.?name|surname|family.?name|nom|apellido|nachname": "last_name",
    r"full.?name|nombre.?completo": "full_name",
    r"\bcity\b|\blocality\b|ciudad|ville|ort": "city",
    r"address.?line.?1|street.?address|street|address": "address_line_1",
    r"address.?line.?2": "address_line_2",
    r"postal|zip|pin.?code|post.?code": "postal_code",
    r"state|province|region": "state_province",
    r"location|standort": "location",
    r"linkedin|linked.?in": "linkedin_url",
    r"github|git.?hub": "github_url",
    r"portfolio|website|sitio": "portfolio_url",
    r"current.?company|present.?employer|current.?employer": "current_company",
    r"graduation.?year|year.?of.?graduation|degree.?year|completed.?year": "graduation_year",
    r"degree.?type|degree.?level|highest.?degree|highest.?qualification|education.?degree": "degree_type",
    r"employment.?type|job.?type|work.?type|desired.?employment": "employment_type",
    # Work authorization & relocation
    r"work.?authoriz|authorized.?to.?work|visa.?status|right.?to.?work|sponsorship|work.?permit": "work_authorization",
    r"reloc|willing.?to.?move|open.?to.?relocation": "willing_to_relocate",
    # Salary & notice
    r"salary|compensation|ctc|pay.?expect|expected.?pay|desired.?salary": "expected_salary",
    r"notice.?period|notice|availability|start.?date|when.?can.?you.?start": "notice_period",
    # Simple Demographics
    r"\bgender\b|\bsex\b": "gender",
    r"disabilit|handicap": "disability_status",
    r"citizen|nationality": "country_of_citizenship",
    r"sponsor|visa.*spons": "requires_sponsorship",
    # Currently working toggle (dateRange~present checkbox)
    r"current(ly)?|i.?am.?currently|presently.?work|still.?work|end.?date.*current|this.?is.?my.?current": "currently_working",
}


def get_best_profile_key_match(field_text: str, profile_keys: list[str]) -> tuple[str, float]:
    import difflib
    best_key = ""
    best_score = 0.0
    
    # Normalize field text
    field_text_clean = field_text.lower().replace("_", " ").replace("-", " ").strip()
    
    for key in profile_keys:
        key_clean = key.lower().replace("_", " ").replace("-", " ").strip()
        
        # Exact word match check
        if field_text_clean == key_clean:
            return key, 1.0
            
        # Character-level similarity
        matcher = difflib.SequenceMatcher(None, field_text_clean, key_clean)
        char_score = matcher.ratio()
        
        # Word token overlap (Jaccard similarity)
        w1 = set(re.findall(r'\b\w+\b', field_text_clean))
        w2 = set(re.findall(r'\b\w+\b', key_clean))
        word_score = 0.0
        if w1 and w2:
            word_score = len(w1.intersection(w2)) / len(w1.union(w2))
            
        score = max(char_score, word_score)
        if score > best_score:
            best_score = score
            best_key = key
            
    return best_key, best_score


async def fill_if_deterministic(target, field: dict, profile: dict, fill_field_fn) -> bool:
    """
    Try to match a field against DETERMINISTIC_FIELD_MAP using
    name, id, aria-label, and placeholder attributes.
    If no regex match, performs fuzzy token similarity matching against profile keys.
    Returns True if filled, False if LLM is needed.
    
    fill_field_fn: async function(target, field_answer_dict) -> bool
    """
    # Collect all matchable text from the field metadata
    matchable_texts = [
        field.get("name", ""),
        field.get("id", ""),
        field.get("aria-label", ""),
        field.get("placeholder", ""),
        field.get("label", ""),
    ]
    combined = " ".join([t for t in matchable_texts if t]).lower()

    # Guard: if the field asks about experience or years, delegate to LLM
    # (except for graduation year or current working check)
    is_exception = any(re.search(pat, combined, re.IGNORECASE) for pat in [
        r"graduation.?year", r"year.?of.?graduation", r"degree.?year", r"completed.?year", r"currently_working"
    ])
    if not is_exception and any(word in combined for word in ["experience", "years", "year", "how many", "how long", "duration", "worked"]):
        logger.info(f"[DeterministicFill] Skipping deterministic fill for potential experience field: '{combined}'")
        return False

    for pattern, profile_key in DETERMINISTIC_FIELD_MAP.items():
        if re.search(pattern, combined, re.IGNORECASE):
            value = _resolve_profile_value(profile, profile_key, field.get("type", "text"))
            if value:
                # Match the expected schema for _fill_field_robust
                await fill_field_fn(target, {
                    "qa_idx": field["qa_idx"],
                    "type": field.get("type", "text"),
                    "answer": value,
                    "label": field.get("aria-label", ""),
                    "selector": "",
                })
                return True

    # Layer 2: Fuzzy matching fallback if regex didn't match
    profile_keys = list(profile.keys()) + [
        "phone_country_code", "first_name", "last_name", "current_company", 
        "current_title", "current_role", "graduation_year", "degree_type", 
        "employment_type", "currently_working", "expected_salary"
    ]
    
    for text in matchable_texts:
        if not text:
            continue
        text_clean = text.lower().strip()
        best_key, score = get_best_profile_key_match(text_clean, profile_keys)
        if score >= 0.85:
            value = _resolve_profile_value(profile, best_key, field.get("type", "text"))
            if value:
                logger.info(f"[DeterministicFill] Fuzzy matched '{text}' to profile key '{best_key}' (score: {score:.2f})")
                await fill_field_fn(target, {
                    "qa_idx": field["qa_idx"],
                    "type": field.get("type", "text"),
                    "answer": value,
                    "label": field.get("aria-label", ""),
                    "selector": "",
                })
                return True
                
    return False


def _resolve_profile_value(profile: dict, key: str, field_type: str = "") -> str:
    if key == "first_name":
        first = profile.get("first_name", "").strip()
        if first:
            return first
        full = profile.get("full_name", "")
        return full.split()[0] if full else ""
    elif key == "last_name":
        last = profile.get("last_name", "").strip()
        if last:
            return last
        full = profile.get("full_name", "")
        parts = full.split(maxsplit=1)
        return parts[1] if len(parts) > 1 else ""
    elif key == "city":
        city = profile.get("city", "").strip()
        if city:
            return city
        loc = profile.get("location", "").strip()
        if loc:
            parts = [p.strip() for p in loc.split(",")]
            if parts:
                return parts[0]
        return ""
    elif key == "phone_country_code":
        code = profile.get("phone_country_code", "")
        if not code:
            return ""
        
        # For text inputs, return just the numeric code (e.g. +91)
        if field_type and field_type not in ("select", "select-one"):
            return code
            
        # Try to append country name for better select matching
        mapping = {
            "+91": "India",
            "+1": "United States",
            "+44": "United Kingdom",
            "+61": "Australia",
            "+971": "United Arab Emirates",
            "+49": "Germany",
            "+33": "France",
            "+81": "Japan",
            "+65": "Singapore",
            "+86": "China",
        }
        
        location = profile.get("location", "").lower()
        if code == "+1" and "canada" in location:
            country = "Canada"
        else:
            country = mapping.get(code)
            
            
        if country:
            formatted_code = f"{country} ({code})"
            logger.info(f"[DeterministicFill] Resolving phone_country_code to: '{formatted_code}'")
            return formatted_code
        logger.info(f"[DeterministicFill] Resolving phone_country_code to raw code: '{code}'")
        return code
    elif key == "country":
        # Try to extract country from location (e.g. "Mumbai, India" -> "India")
        loc = profile.get("location", "")
        if loc:
            parts = [p.strip() for p in loc.split(",")]
            if parts:
                return parts[-1]
        
        # Fallback to phone_country_code mapping
        code = profile.get("phone_country_code", "")
        if code:
            mapping = {
                "+91": "India",
                "+1": "United States",
                "+44": "United Kingdom",
                "+61": "Australia",
                "+971": "United Arab Emirates",
                "+49": "Germany",
                "+33": "France",
                "+81": "Japan",
                "+65": "Singapore",
                "+86": "China",
            }
            return mapping.get(code, "")
        return ""
    elif key == "current_company":
        work_exp = profile.get("work_experience", [])
        if work_exp and isinstance(work_exp, list):
            first = work_exp[0]
            if isinstance(first, dict):
                return first.get("company", "")
        return ""
    elif key in ("current_title", "current_role"):
        work_exp = profile.get("work_experience", [])
        if work_exp and isinstance(work_exp, list):
            first = work_exp[0]
            if isinstance(first, dict):
                return first.get("title") or first.get("role") or ""
        return ""
    elif key == "graduation_year":
        edu = profile.get("education", [])
        if edu and isinstance(edu, list):
            first = edu[0]
            if isinstance(first, dict):
                val = first.get("year") or first.get("end_date") or first.get("end_year") or ""
                return str(val)
        return ""
    elif key == "degree_type":
        edu = profile.get("education", [])
        if edu and isinstance(edu, list):
            first = edu[0]
            if isinstance(first, dict):
                return first.get("degree") or first.get("field") or ""
        return ""
    elif key == "employment_type":
        return "Full-time"
    elif key == "willing_to_relocate":
        val = profile.get("willing_to_relocate")
        if val is True:
            return "Yes"
        elif val is False:
            return "No"
        return ""
    elif key == "work_authorization":
        val = profile.get("work_authorization", "").strip()
        return val if val else "Will discuss during interview"
    elif key == "currently_working":
        # For the LinkedIn dateRange~present checkbox: always True (currently employed)
        work_exp = profile.get("work_experience", [])
        if work_exp and isinstance(work_exp, list):
            first = work_exp[0]
            if isinstance(first, dict):
                end = first.get("end_date") or first.get("end_year") or ""
                # If end date is empty, 'present', 'current' etc → still employed
                if not end or str(end).lower() in ("present", "current", "now", "", "ongoing"):
                    return "true"
        return ""
    elif key == "location":
        city = profile.get("city", "").strip()
        state = profile.get("state_province", "").strip()
        country = profile.get("country", "").strip()
        parts = [p for p in [city, state, country] if p]
        if parts:
            return ", ".join(parts)
        return profile.get("location", "").strip()
    elif key == "expected_salary":
        val = profile.get("expected_salary", "")
        return str(val) if val else "Negotiable"
    elif key == "notice_period":
        val = profile.get("notice_period", "")
        return str(val) if val else ""
    elif key == "total_years_experience":
        return str(profile.get("total_years_experience", ""))
    val = profile.get(key)
    return str(val) if val is not None else ""

