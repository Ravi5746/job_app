import re

DETERMINISTIC_FIELD_MAP = {
    # English + common i18n patterns
    r"phone|mobile|telefon|téléphone|telefono|celular": "phone",
    r"country.?code|dial.?code|calling.?code|prefix": "phone_country_code",
    r"email|e-mail|correo|courriel": "email",
    r"first.?name|given.?name|prénom|nombre|vorname": "first_name",
    r"last.?name|surname|family.?name|nom|apellido|nachname": "last_name",
    r"full.?name|nombre.?completo": "full_name",
    r"city|location|ciudad|ville|standort|ort": "location",
    r"linkedin|linked.?in": "linkedin_url",
    r"github|git.?hub": "github_url",
    r"portfolio|website|sitio": "portfolio_url",
}


async def fill_if_deterministic(target, field: dict, profile: dict, fill_field_fn) -> bool:
    """
    Try to match a field against DETERMINISTIC_FIELD_MAP using
    name, id, aria-label, and placeholder attributes.
    Returns True if filled, False if LLM is needed.
    
    fill_field_fn: async function(target, field_answer_dict) -> bool
    """
    # Collect all matchable text from the field metadata
    matchable_texts = [
        field.get("name", ""),
        field.get("id", ""),
        field.get("aria-label", ""),
        field.get("placeholder", ""),
    ]
    combined = " ".join([t for t in matchable_texts if t]).lower()

    for pattern, profile_key in DETERMINISTIC_FIELD_MAP.items():
        if re.search(pattern, combined, re.IGNORECASE):
            value = _resolve_profile_value(profile, profile_key)
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
    return False


def _resolve_profile_value(profile: dict, key: str) -> str:
    if key == "first_name":
        full = profile.get("full_name", "")
        return full.split()[0] if full else ""
    elif key == "last_name":
        full = profile.get("full_name", "")
        parts = full.split(maxsplit=1)
        return parts[1] if len(parts) > 1 else ""
    elif key == "phone_country_code":
        code = profile.get("phone_country_code", "")
        if not code:
            return ""
        
        # If location is available, try to append country name for better select matching
        location = profile.get("location", "").lower()
        if location:
            mapping = {
                "+91": "India",
                "+1": "United States" if "united states" in location or "usa" in location or "us" in location.split() else "Canada" if "canada" in location else "",
                "+44": "United Kingdom",
                "+61": "Australia",
                "+971": "United Arab Emirates",
                "+49": "Germany",
                "+33": "France",
                "+81": "Japan",
                "+65": "Singapore",
                "+86": "China",
            }
            country = mapping.get(code)
            if country:
                return f"{country} ({code})"
        return code
    val = profile.get(key)
    return str(val) if val is not None else ""
