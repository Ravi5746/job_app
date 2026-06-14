import pytest
from unittest.mock import MagicMock

def test_detect_ats_url():
    from app.services.field_intelligence.ats_detector import detect_ats
    
    mock_page = MagicMock()
    mock_page.url = "https://jobs.lever.co/google/12345"
    assert detect_ats(mock_page) == "lever"

    mock_page.url = "https://boards.greenhouse.io/facebook/jobs/98765"
    assert detect_ats(mock_page) == "greenhouse"

    mock_page.url = "https://example.com/random"
    assert detect_ats(mock_page) == "unknown"

@pytest.mark.asyncio
async def test_detect_ats_dom():
    from app.services.field_intelligence.ats_detector import detect_ats_dom
    from unittest.mock import AsyncMock
    
    # 1. Test when URL matches
    mock_page = MagicMock()
    mock_page.url = "https://jobs.lever.co/google/12345"
    ats = await detect_ats_dom(mock_page)
    assert ats == "lever"

    # 2. Test when URL doesn't match, fallback to DOM signature query
    mock_page = MagicMock()
    mock_page.url = "https://customdomainjobboard.com/careers"
    
    # We want to match smartrecruiters signature: "[data-test='job-apply']"
    # To do that, the locator query for that selector should return count > 0, others return 0.
    def mock_locator(selector):
        loc = MagicMock()
        if selector == "[data-test='job-apply']":
            loc.count = AsyncMock(return_value=1)
        else:
            loc.count = AsyncMock(return_value=0)
        return loc

    mock_page.locator = MagicMock(side_effect=mock_locator)
    
    ats = await detect_ats_dom(mock_page)
    assert ats == "smartrecruiters"
