import logging
from playwright.async_api import Locator

logger = logging.getLogger(__name__)

DEFAULTS = {
    "text": "Test",
    "email": "test@test.com",
    "tel": "0000000000",
    "url": "https://test.com",
    "number": "1",
    "textarea": "N/A",
}

async def fake_fill_field(locator: Locator, field: dict):
    field_type = (field.get("field_type") or field.get("type") or "text").lower()
    
    # 1. Input fields
    if field_type in ["text", "email", "tel", "url", "number", "textarea"]:
        default_val = DEFAULTS.get(field_type, "Test")
        try:
            await locator.fill(default_val)
            logger.info(f"Filled {field.get('label')} with default '{default_val}'")
        except Exception as e:
            logger.error(f"Failed to fill text locator for {field.get('label')}: {e}")

    # 2. Select fields
    elif field_type == "select":
        try:
            # We select first option index=1 (usually index=0 is placeholder/empty)
            await locator.select_option(index=1)
            logger.info(f"Selected index 1 option for {field.get('label')}")
        except Exception as e:
            try:
                await locator.select_option(index=0)
            except Exception:
                logger.error(f"Failed to select option for {field.get('label')}: {e}")

    # 3. Radio buttons
    elif field_type == "radio":
        try:
            # Radio inputs might be inside a group; attempt to click the first choice
            await locator.first.click()
            logger.info(f"Clicked first radio option for {field.get('label')}")
        except Exception as e:
            logger.error(f"Failed to click radio option for {field.get('label')}: {e}")

    # 4. Checkbox
    elif field_type == "checkbox":
        try:
            await locator.check()
            logger.info(f"Checked checkbox for {field.get('label')}")
        except Exception as e:
            logger.error(f"Failed to check checkbox for {field.get('label')}: {e}")
