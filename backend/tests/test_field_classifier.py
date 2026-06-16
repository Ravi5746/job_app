def test_field_classifier():
    from app.services.field_intelligence.field_classifier import classify
    
    # 1. Regex test (first name)
    assert classify("First Name", "firstname", "first_name", "First Name") == "first_name"
    
    # 2. Static lookup test
    assert classify("Your Legal Name", "", "", "") == "full_name"
    
    # 3. difflib fuzzy matching
    assert classify("Phone Number", "", "", "") == "phone"
    
    # 4. Question Category Regex
    assert classify("Do you have any criminal convictions?", "", "", "") == "screening_question"
    assert classify("Are you legally authorized to work in the US?", "", "", "") == "work_authorization"
    assert classify("What is your race or ethnicity?", "", "", "") == "eeo_question"
    assert classify("Why do you want to work here?", "", "", "") == "custom_question"
    
    # 5. Fallback
    assert classify("Random question 123", "", "", "") == "random question 123"
    assert classify("", "", "", "") == "uncategorized"

    # 6. Casing, trailing whitespace, and synonyms
    assert classify("Resume ") == "resume"
    assert classify("Resume\n") == "resume"
    assert classify("履歴書/CV") == "resume"
    assert classify("Name") == "full_name"
    assert classify("fullname") == "full_name"
    assert classify("téléphone") == "phone"
    assert classify("resum") == "resume"

