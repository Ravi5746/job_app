def test_submit_guard():
    from app.services.field_intelligence.submit_guard import is_submit_button
    
    assert is_submit_button("Submit Application") is True
    assert is_submit_button("Apply Now") is True
    assert is_submit_button("Submit") is True
    assert is_submit_button("Next Step") is False
    assert is_submit_button("Save and Continue") is False
    assert is_submit_button("Review Application") is False
    assert is_submit_button("Random Button") is False
