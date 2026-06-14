import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_fake_fill_field_input():
    from app.services.field_intelligence.fake_filler import fake_fill_field
    
    # Text input
    mock_locator = AsyncMock()
    mock_locator.fill = AsyncMock()
    
    field = {
        "field_type": "text",
        "required": True,
        "label": "First Name"
    }
    
    await fake_fill_field(mock_locator, field)
    mock_locator.fill.assert_called_once_with("Test")

@pytest.mark.asyncio
async def test_fake_fill_field_select():
    from app.services.field_intelligence.fake_filler import fake_fill_field
    
    # Select input
    mock_locator = AsyncMock()
    mock_locator.select_option = AsyncMock()
    
    field = {
        "field_type": "select",
        "required": True,
        "label": "State"
    }
    
    await fake_fill_field(mock_locator, field)
    mock_locator.select_option.assert_called_once_with(index=1)

@pytest.mark.asyncio
async def test_fake_fill_field_checkbox():
    from app.services.field_intelligence.fake_filler import fake_fill_field
    
    # Checkbox input
    mock_locator = AsyncMock()
    mock_locator.check = AsyncMock()
    
    field = {
        "field_type": "checkbox",
        "required": True,
        "label": "Agree to Terms"
    }
    
    await fake_fill_field(mock_locator, field)
    mock_locator.check.assert_called_once()


@pytest.mark.asyncio
async def test_fake_fill_field_using_type_attribute():
    from app.services.field_intelligence.fake_filler import fake_fill_field
    
    # Passing 'type' instead of 'field_type'
    mock_locator = AsyncMock()
    mock_locator.select_option = AsyncMock()
    
    field = {
        "type": "select",
        "required": True,
        "label": "Source"
    }
    
    await fake_fill_field(mock_locator, field)
    mock_locator.select_option.assert_called_once_with(index=1)

