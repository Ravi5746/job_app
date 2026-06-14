import re

SUBMIT_PATTERNS = [
    r"\bsubmit\b",
    r"\bsend\s+application\b",
    r"\bapply\s+now\b",
    r"^apply$",
    r"\bconfirm\b",
    r"\bfinish\b",
]

SAFE_PATTERNS = [
    r"\bnext\b",
    r"\bcontinue\b",
    r"\bsave\b",
    r"\breview\b",
]

def is_submit_button(button_text: str) -> bool:
    text = button_text.lower().strip()
    
    # Check if matches any safe pattern
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, text):
            return False
            
    # Check if matches submit pattern
    for pattern in SUBMIT_PATTERNS:
        if re.search(pattern, text):
            return True
            
    return False
