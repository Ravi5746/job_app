import logging
import re
from playwright.async_api import Locator

logger = logging.getLogger(__name__)

class BaseBrowserHandler:
    async def trigger_events(self, el: Locator):
        try:
            await el.evaluate(
                "el => { "
                "el.dispatchEvent(new Event('input', { bubbles: true })); "
                "el.dispatchEvent(new Event('change', { bubbles: true })); "
                "}"
            )
        except Exception as e:
            logger.debug(f"Failed to trigger events: {e}")

class LocationTypeaheadHandler(BaseBrowserHandler):
    # All known LinkedIn typeahead dropdown selectors
    DROPDOWN_SELECTORS = [
        ".artdeco-typeahead__results-list",
        ".artdeco-typeahead__results",
        ".artdeco-typeahead__dropdown",
        ".search-basic-typeahead",
        "[role='listbox']",
        "ul.artdeco-typeahead__results-list",
    ]
    # Individual suggestion item selectors
    ITEM_SELECTORS = [
        ".artdeco-typeahead__results-list li",
        ".artdeco-typeahead__results li",
        "[role='listbox'] [role='option']",
        "[role='option']",
        ".artdeco-typeahead__result",
        ".search-basic-typeahead__item",
    ]

    async def _wait_for_dropdown(self, target, timeout_ms: int = 4000) -> bool:
        """Wait until at least one typeahead suggestion is visible."""
        import asyncio
        deadline = timeout_ms / 1000
        elapsed = 0.0
        poll = 0.2
        while elapsed < deadline:
            for sel in self.DROPDOWN_SELECTORS:
                try:
                    loc = target.locator(sel)
                    if await loc.count() > 0 and await loc.first.is_visible():
                        return True
                except Exception:
                    pass
            await asyncio.sleep(poll)
            elapsed += poll
        return False

    async def _click_first_suggestion(self, target) -> bool:
        """Click the first visible suggestion item in the dropdown."""
        for sel in self.ITEM_SELECTORS:
            try:
                items = target.locator(sel)
                count = await items.count()
                for i in range(count):
                    item = items.nth(i)
                    if await item.is_visible(timeout=300):
                        text = (await item.inner_text()).strip()
                        logger.info(f"[LocationTypeaheadHandler] Clicking suggestion: '{text}'")
                        await item.click(timeout=2000)
                        return True
            except Exception:
                continue
        return False

    async def _get_field_value(self, el: Locator) -> str:
        try:
            return (await el.input_value()).strip()
        except Exception:
            return ""

    async def fill(self, target, el: Locator, value: str) -> bool:
        """
        Fill a LinkedIn location typeahead field by:
        1. Clearing the field and typing the value character-by-character
        2. Waiting for the autocomplete dropdown to actually appear (up to 4s)
        3. Clicking the first visible suggestion
        4. Verifying the field has a real value after selection
        5. Retrying with city-only fallback if full string gets no dropdown
        """
        # Try with the full value first, then fall back to city-only
        attempts = [value]
        city_only = value.split(",")[0].strip()
        if city_only and city_only != value:
            attempts.append(city_only)

        for attempt_val in attempts:
            try:
                logger.info(f"[LocationTypeaheadHandler] Typing location: '{attempt_val}'")

                # --- Clear and type ---
                await el.scroll_into_view_if_needed()
                await el.click(timeout=2000)
                await el.press("Control+a")
                await el.press("Delete")
                await target.wait_for_timeout(150)

                # Type char-by-char to trigger LinkedIn's JS event listeners
                for char in attempt_val:
                    await el.type(char, delay=60)

                # --- Wait for dropdown to appear (up to 4s) ---
                appeared = await self._wait_for_dropdown(target, timeout_ms=4000)

                if appeared:
                    clicked = await self._click_first_suggestion(target)
                    if clicked:
                        await target.wait_for_timeout(400)
                        final_value = await self._get_field_value(el)
                        if final_value:
                            logger.info(
                                f"[LocationTypeaheadHandler] ✅ Location set to: '{final_value}'"
                            )
                            await self.trigger_events(el)
                            return True
                        else:
                            logger.warning(
                                "[LocationTypeaheadHandler] Clicked suggestion but field is empty. Retrying..."
                            )
                    else:
                        logger.warning(
                            f"[LocationTypeaheadHandler] Dropdown appeared but no clickable item found for '{attempt_val}'."
                        )
                else:
                    logger.warning(
                        f"[LocationTypeaheadHandler] No dropdown appeared for '{attempt_val}'. "
                        "Falling back to ArrowDown+Enter."
                    )
                    # Last-resort: keyboard navigation
                    await el.press("ArrowDown")
                    await target.wait_for_timeout(2000)
                    await el.press("Enter",delay=900)
                    await target.wait_for_timeout(900)
                    final_value = await self._get_field_value(el)
                    if final_value:
                        logger.info(
                            f"[LocationTypeaheadHandler] ✅ Keyboard fallback set to: '{final_value}'"
                        )
                        await self.trigger_events(el)
                        return True

            except Exception as e:
                logger.error(f"[LocationTypeaheadHandler] Error with '{attempt_val}': {e}")
                continue

        logger.error(
            f"[LocationTypeaheadHandler] ❌ Failed to set location for all attempts: {attempts}"
        )
        return False


class PhoneCountryHandler(BaseBrowserHandler):
    async def fill(self, target, el: Locator, phone_code: str, profile: dict) -> bool:
        try:
            logger.info(f"[PhoneCountryHandler] Selection code: '{phone_code}'")
            await el.scroll_into_view_if_needed()
            
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
            
            location = (profile.get("location") or profile.get("country") or "").lower()
            if phone_code == "+1" and "canada" in location:
                country_name = "Canada"
            else:
                country_name = mapping.get(phone_code, "")
                
            options = await el.evaluate(
                "el => Array.from(el.options).map(o => ({v: o.value, t: o.text.trim()}))"
            )
            
            selected = False
            for opt in options:
                opt_text = opt["t"].lower()
                if country_name and country_name.lower() in opt_text:
                    await el.select_option(value=opt["v"])
                    selected = True
                    logger.info(f"[PhoneCountryHandler] Selected by country name '{country_name}': {opt['t']}")
                    break
                    
            if not selected:
                digits_target = re.sub(r'\D', '', phone_code)
                for opt in options:
                    opt_text = opt["t"].lower()
                    opt_val = opt["v"].lower()
                    digits_opt_text = re.sub(r'\D', '', opt_text)
                    digits_opt_val = re.sub(r'\D', '', opt_val)
                    
                    if digits_target in (digits_opt_text, digits_opt_val):
                        await el.select_option(value=opt["v"])
                        selected = True
                        logger.info(f"[PhoneCountryHandler] Selected by code match '{phone_code}': {opt['t']}")
                        break
                        
            if not selected and options:
                logger.warning(f"[PhoneCountryHandler] No exact match for code '{phone_code}'. Selecting first non-empty option.")
                await el.select_option(value=options[0]["v"])
                
            await self.trigger_events(el)
            return True
        except Exception as e:
            logger.error(f"[PhoneCountryHandler] Error: {e}")
            return False
