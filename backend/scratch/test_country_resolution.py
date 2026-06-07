import sys
sys.path.append('.')

from app.services.automation.agent.deterministic_fill import _resolve_profile_value

def test_resolution():
    # Test case 1: India code with India location
    profile1 = {
        "phone_country_code": "+91",
        "location": "Ahmedabad, Gujarat, India"
    }
    res1 = _resolve_profile_value(profile1, "phone_country_code")
    print(f"Test 1 (India): expected='India (+91)', got='{res1}'")
    assert res1 == "India (+91)"

    # Test case 2: US code with US location
    profile2 = {
        "phone_country_code": "+1",
        "location": "New York, USA"
    }
    res2 = _resolve_profile_value(profile2, "phone_country_code")
    print(f"Test 2 (US): expected='United States (+1)', got='{res2}'")
    assert res2 == "United States (+1)"

    # Test case 3: US code with Canada location
    profile3 = {
        "phone_country_code": "+1",
        "location": "Toronto, Canada"
    }
    res3 = _resolve_profile_value(profile3, "phone_country_code")
    print(f"Test 3 (Canada): expected='Canada (+1)', got='{res3}'")
    assert res3 == "Canada (+1)"

    # Test case 4: Unmapped code or empty location
    profile4 = {
        "phone_country_code": "+44",
        "location": ""
    }
    res4 = _resolve_profile_value(profile4, "phone_country_code")
    print(f"Test 4 (No location): expected='+44', got='{res4}'")
    assert res4 == "+44"

    print("ALL TESTS PASSED!")

if __name__ == "__main__":
    test_resolution()
