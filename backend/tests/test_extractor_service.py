import pytest
from unittest.mock import AsyncMock, MagicMock, patch

def test_compute_dom_hash():
    from app.services.field_intelligence.extractor_service import compute_dom_hash
    
    fields = [
        {"label": "First Name", "type": "text", "required": True},
        {"label": "Email", "type": "email", "required": True}
    ]
    h1 = compute_dom_hash(fields, "Page text content")
    h2 = compute_dom_hash(fields, "Page text content")
    assert h1 == h2
    
    # Change snippet
    h3 = compute_dom_hash(fields, "Different page content")
    assert h1 != h3

    # Change field options
    fields_with_opts = [
        {"label": "Gender", "type": "select", "required": False, "options": ["Male", "Female"]},
    ]
    h4 = compute_dom_hash(fields_with_opts, "EEO Info")
    fields_different_opts = [
        {"label": "Gender", "type": "select", "required": False, "options": ["Male", "Female", "Other"]},
    ]
    h5 = compute_dom_hash(fields_different_opts, "EEO Info")
    assert h4 != h5
