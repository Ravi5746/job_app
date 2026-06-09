import logging
import re
from urllib.parse import urlparse
from typing import Optional
from playwright.async_api import Page
from .base_handler import BasePlatformHandler

logger = logging.getLogger(__name__)

class IndeedHandler(BasePlatformHandler):
    async def get_active_target(self, page: Page) -> tuple:
        indeed_frame = await self.service._find_indeed_frame(page)
        if indeed_frame:
            form_loc = indeed_frame.locator("form").first
            if await form_loc.count() > 0:
                return indeed_frame, form_loc
            return indeed_frame, indeed_frame.locator("body")
        return page, page.locator("body")

    async def detect_easy_apply_step(self, target) -> str:
        try:
            modal = await self.service._get_active_modal(target)
            curr_target = modal if modal else target
            if hasattr(curr_target, "goto"):
                container_text = (await curr_target.locator("body").inner_text()).lower()
            else:
                container_text = (await curr_target.inner_text()).lower()

            success_signals = [
                "application sent",
                "application was sent",
                "successfully submitted",
                "your application was submitted",
                "thank you for applying",
                "application submitted",
            ]
            if any(s in container_text for s in success_signals):
                return "success"

            # Submit button → review page
            submit_selectors = [
                "button:has-text('Submit application')",
                "button[aria-label*='Submit application']",
                "button:text-is('Submit')",
                "button:text-is('Submit Application')",
                "button:text-is('Send Application')",
                "button#form-action-send",
                "button[data-testid='submit-application-button']",
            ]
            for s_sel in submit_selectors:
                try:
                    if await curr_target.locator(s_sel).count() > 0:
                        return "review"
                except Exception:
                    pass

            # Resume upload — only when the upload UI card / button is visible
            for sel in [
                "button:has-text('Upload resume')",
                "button:has-text('Choose file')",
                "[data-test-resume-upload]",
                "input[type='file'][accept*='pdf']",
                "input[name='resume']",
                "input[name='file']",
                "[data-testid='resume-upload']",
                ".file-upload-input",
            ]:
                try:
                    if await curr_target.locator(sel).count() > 0:
                        return "resume_upload"
                except Exception:
                    pass

            # Contact info
            for sel in [
                "input[id*='phoneNumber']",
                "input[name*='phoneNumber']",
                "input[type='tel']",
                "input[name*='firstName']",
                "input[name*='first_name']",
                "input[name*='first-name']",
                "input[data-testid*='first-name']",
                "input[name*='last-name']",
                "input[data-testid*='last-name']",
            ]:
                try:
                    if await curr_target.locator(sel).count() > 0:
                        return "contact_info"
                except Exception:
                    pass

            # Additional questions (text inputs, selects, radios, textareas)
            for sel in [
                "fieldset",
                "select",
                "input[type='radio']",
                "input[type='checkbox']",
                "textarea",
                "input:not([type='radio']):not([type='checkbox']):not([type='file'])"
                ":not([type='hidden']):not([type='submit'])",
            ]:
                try:
                    if await curr_target.locator(sel).count() > 0:
                        return "questions"
                except Exception:
                    pass

        except Exception as exc:
            logger.error(f"[Indeed StepDetector] Error: {exc}")

        return "unknown"

    async def click_next_or_review(self, target) -> bool:
        modal_locator = await self.service._get_active_modal(target)
        curr_target = modal_locator if modal_locator else target

        clicked = await self._click_first_visible(
            curr_target,
            [
                "button:has-text('Next')",
                "button:has-text('Continue')",
                "button:has-text('Review')",
                "button[aria-label*='Continue to']",
                "button[aria-label*='Next']",
                "button#form-action-continue",
                "button[class*='continue']",
                "button[class*='next']",
            ],
            timeout_ms=1500
        )
        if clicked:
            logger.info("[Indeed Nav] Clicked navigation button successfully.")
            await self.service._wait_for_page_settle(target)
            return True
        return False

    async def handle_review_step(self, target, modal_locator, db, job) -> bool:
        curr_target = modal_locator if modal_locator else target

        submit_selectors = [
            "button:has-text('Submit application')",
            "button[aria-label*='Submit application']",
            "button:text-is('Submit')",
            "button:text-is('Submit Application')",
            "button:text-is('Send Application')",
            "button#form-action-send",
            "button[data-testid='submit-application-button']",
        ]
        submit_btn = await self._find_first_visible(curr_target, submit_selectors, timeout_ms=2000)

        if submit_btn:
            await submit_btn.click()
            logger.info("[Indeed Review] Clicked Submit application. Waiting for confirmation...")

            # Wait up to 6 seconds for success screen
            for check in range(6):
                await target.wait_for_timeout(1000)
                next_step = await self.detect_easy_apply_step(target)
                if next_step == "success":
                    logger.info("[Indeed Review] Success screen detected!")
                    break

            job.status = "applied"
            db.commit()
            return True
        else:
            logger.warning("[Indeed Review] Submit application button not found or not visible.")
            return False

    async def is_session_expired(self, page: Page) -> bool:
        return any(kw in page.url for kw in ["indeed.com/auth", "indeed.com/login", "secure.indeed.com"])

    async def dismiss_popups(self, page: Page) -> None:
        for p_sel in [
            "button#onetrust-accept-btn-handler",
            "button.gnav-CookieConsent-accept",
            "button[aria-label='Dismiss']",
            "button.modal__dismiss",
            ".icl-CloseButton",
        ]:
            try:
                btn = page.locator(p_sel).first
                if await btn.is_visible(timeout=1000):
                    await btn.click()
                    await page.wait_for_timeout(800)
            except Exception:
                continue
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

    async def find_apply_button(self, page: Page):
        for sel in [
            "button#indeedApplyButton",
            "[data-testid='indeedApplyButton-test']",
            "button[aria-label='Apply with Indeed']",
            "button:has-text('Apply with Indeed')",
            "button.indeed-apply-button",
            "[data-testid='indeed-apply-button']",
            "button:has-text('Apply now')",
            "button:has-text('Apply Now')",
            "a:has-text('Apply Now')",
            "span.indeed-apply-button-inner button",
            "span.indeed-apply-button-label",
            "button[aria-label='Apply now']",
        ]:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    logger.info(f"Indeed Apply button found via selector: {sel}")
                    return btn
            except Exception:
                continue
        return None

    async def wait_for_apply_interface(self, page: Page) -> bool:
        app_interface_found = False
        for check in range(10):  # up to 10 seconds
            if "apply.indeed.com" in page.url or "indeed.com/apply" in page.url:
                app_interface_found = True
                break
            frame = await self.service._find_indeed_frame(page)
            if frame:
                app_interface_found = True
                break
            if await page.locator("[role='dialog']:visible, form:visible").count() > 0:
                app_interface_found = True
                break
            await page.wait_for_timeout(1000)
        
        if app_interface_found:
            logger.info("[Indeed Apply] Indeed application interface detected.")
            return True
        
        logger.warning("[Indeed Apply] Indeed application interface not detected. Proceeding blindly.")
        return False

    async def is_external_redirect(self, page: Page, original_domain: str) -> Optional[dict]:
        current_domain = urlparse(page.url).netloc
        if "indeed" not in current_domain and current_domain != original_domain:
            return {
                "status": "warning",
                "message": "External form detected (Google Form / Company Portal). Complete manually.",
                "url": page.url,
            }
        return None

    async def fill_phone_country_code(self, target, profile: dict) -> bool:
        """
        Custom combobox interaction logic for selecting Indeed's phone country code.
        """
        phone_country_code = profile.get("phone_country_code", "").strip()
        if not phone_country_code:
            logger.info("[Indeed CountryCode] No phone_country_code in profile. Defaulting to +1.")
            phone_country_code = "+1"

        # Find the active modal/form container
        modal_locator = await self.service._get_active_modal(target)
        curr_target = modal_locator if modal_locator else target

        # 1. Locate the combobox
        combobox = curr_target.locator("div[role='combobox']").first
        if await combobox.count() == 0:
            logger.debug("[Indeed CountryCode] No combobox found in current step/target.")
            return False

        # Verify it is indeed the phone country select combobox (by label or parent text/aria attribute)
        try:
            combobox_text = (await combobox.inner_text()).strip()
            # If the combobox already displays our target country code, skip clicking!
            code_digits = re.sub(r"\D", "", phone_country_code)
            curr_digits = re.sub(r"\D", "", combobox_text)
            if curr_digits == code_digits:
                logger.info(f"[Indeed CountryCode] Already selected code: {combobox_text} (matches target +{code_digits}). Skipping selection.")
                return True
        except Exception as e:
            logger.debug(f"[Indeed CountryCode] Error checking current selected value: {e}")

        # 2. Click the combobox to open the dropdown listbox
        try:
            logger.info("[Indeed CountryCode] Clicking combobox to show dropdown options...")
            await combobox.click()
            await target.wait_for_timeout(500)
        except Exception as e:
            logger.error(f"[Indeed CountryCode] Failed to click combobox: {e}")
            return False

        # 3. Locate the listbox and matching option
        try:
            # We want to match f"+{code_digits}" in the text of the options
            target_str = f"+{code_digits}"
            options = curr_target.locator("ul[role='listbox'] li[role='option'], [role='listbox'] [role='option']")
            opt_count = await options.count()
            logger.debug(f"[Indeed CountryCode] Found {opt_count} options in listbox. Searching for '{target_str}'...")

            for i in range(opt_count):
                opt = options.nth(i)
                opt_text = await opt.inner_text()
                if target_str in opt_text:
                    logger.info(f"[Indeed CountryCode] Found matching option '{opt_text.strip()}' at index {i}. Clicking it.")
                    await opt.scroll_into_view_if_needed()
                    await opt.click()
                    await target.wait_for_timeout(500)
                    return True

            # Fallback to click based on data-testid attribute if mapping exists
            country_mapping = {
                "1": "US",     # United States / Canada
                "91": "IN",    # India
                "44": "GB",    # United Kingdom
                "61": "AU",    # Australia
                "49": "DE",    # Germany
                "33": "FR",    # France
            }
            iso_code = country_mapping.get(code_digits)
            if iso_code:
                fallback_opt = curr_target.locator(f"li[data-testid='country-select-{iso_code}']").first
                if await fallback_opt.count() > 0:
                    logger.info(f"[Indeed CountryCode] Found option via fallback data-testid='country-select-{iso_code}'. Clicking it.")
                    await fallback_opt.scroll_into_view_if_needed()
                    await fallback_opt.click()
                    await target.wait_for_timeout(500)
                    return True

            logger.warning(f"[Indeed CountryCode] Could not find any option matching '{target_str}'.")
            # Close the combobox by clicking it again
            await combobox.click()
        except Exception as e:
            logger.error(f"[Indeed CountryCode] Error selecting country code option: {e}")
            # Try to close combobox
            try:
                await combobox.click()
            except Exception:
                pass

        return False

