import logging
import re
from urllib.parse import urlparse
from typing import Optional
from playwright.async_api import Page
from .base_handler import BasePlatformHandler

logger = logging.getLogger(__name__)

class LinkedInHandler(BasePlatformHandler):
    async def get_active_target(self, page: Page) -> tuple:
        modal_selectors = [
            ".jobs-easy-apply-modal",
            ".artdeco-modal",
            "[role='dialog']",
            "div[role='region'][aria-label*='progress']",
            "div[role='region'][aria-label*='application']",
        ]
        for m_sel in modal_selectors:
            try:
                loc = page.locator(f"{m_sel}:visible")
                if await loc.count() > 0:
                    return page, loc.first
            except Exception:
                continue
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
            ]
            if any(s in container_text for s in success_signals):
                return "success"

            # Submit button → review page
            has_review = False
            submit_selectors = [
                "button:has-text('Submit application')",
                "button[aria-label*='Submit application']",
                "button[data-control-name='submit_unify']",
            ]
            for s_sel in submit_selectors:
                try:
                    if await curr_target.locator(s_sel).count() > 0:
                        has_review = True
                        break
                except Exception:
                    pass
            if has_review:
                return "review"

            # Resume upload — only when the upload UI card / button is visible
            has_resume_upload = False
            for sel in [
                ".jobs-document-upload-redesign-card__container",
                "label[class*='document-upload']",
                "label:has-text('Upload resume')",
                "button:has-text('Upload resume')",
                "button:has-text('Choose file')",
                "[data-test-resume-upload]",
                "input[type='file']",
                "[class*='document-upload']",
                "[data-test-document-upload-card]",
                "[data-testid*='resume-upload']",
                "input[name='resume']",
                "input[name='file']",
            ]:
                try:
                    if await curr_target.locator(sel).count() > 0:
                        has_resume_upload = True
                        break
                except Exception:
                    pass

            # Contact info
            has_contact_info = False
            for sel in [
                "input[id*='phoneNumber']",
                "input[name*='phoneNumber']",
                "input[type='tel']",
                "select[id*='phoneCountryCode']",
            ]:
                try:
                    if await curr_target.locator(sel).count() > 0:
                        has_contact_info = True
                        break
                except Exception:
                    pass

            # Additional questions (text inputs, selects, radios, textareas)
            has_questions = False
            for sel in [
                "fieldset",
                ".jobs-easy-apply-form-section__grouping",
                "select",
                "input[type='radio']",
                "input[type='checkbox']",
                "textarea",
                "input:not([type='radio']):not([type='checkbox']):not([type='file'])"
                ":not([type='hidden']):not([type='submit'])",
            ]:
                try:
                    if await curr_target.locator(sel).count() > 0:
                        has_questions = True
                        break
                except Exception:
                    pass

            if has_resume_upload:
                return "resume_upload"
            if has_questions:
                return "questions"
            if has_contact_info:
                return "contact_info"

        except Exception as exc:
            logger.error(f"[LinkedIn StepDetector] Error: {exc}")

        return "unknown"

    async def click_next_or_review(self, target) -> bool:
        modal_locator = await self.service._get_active_modal(target)
        curr_target = modal_locator if modal_locator else target

        clicked = await self._click_first_visible(
            curr_target,
            [
                "button:has-text('Save')",
                "button:has-text('save')",
                "button[aria-label*='Save']",
                "button[aria-label*='save']",
                "button:has-text('Next')",
                "button:has-text('Continue')",
                "button:has-text('Review')",
                "button[aria-label*='Continue to']",
                "button[aria-label*='Next']",
                "button[data-easy-apply-next-button]",
                "button[data-control-name='continue']",
                "button[data-control-name='review']",
            ],
            timeout_ms=1500
        )
        if clicked:
            logger.info("[LinkedIn Nav] Clicked navigation button successfully.")
            await self.service._wait_for_page_settle(target)
            return True
        return False

    async def handle_review_step(self, target, modal_locator, db, job) -> bool:
        curr_target = modal_locator if modal_locator else target

        # Optionally uncheck the "Follow company" checkbox
        try:
            follow_cb = curr_target.locator(
                "input[type='checkbox'][id*='follow'], "
                "input[type='checkbox'][name*='follow']"
            ).first
            if await follow_cb.count() > 0 and await follow_cb.is_visible(timeout=1000):
                if await follow_cb.is_checked():
                    await follow_cb.click(force=True)
                    await target.wait_for_timeout(200)
        except Exception:
            pass

        # Wait for the page to fully settle before attempting Submit
        # This prevents TargetClosedError when the modal closes unexpectedly
        try:
            await target.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        await target.wait_for_timeout(1500)

        submit_selectors = [
            "button:has-text('Submit application')",
            "button[aria-label*='Submit application']",
            "button:has-text('Submit')",
            "button[data-control-name='submit_unify']",
        ]

        # Retry finding and clicking submit up to 3 times to handle transient modal state
        for attempt in range(3):
            submit_btn = await self._find_first_visible(curr_target, submit_selectors, timeout_ms=2000)

            if submit_btn:
                try:
                    await submit_btn.scroll_into_view_if_needed()
                    await target.wait_for_timeout(300)
                    await submit_btn.click(timeout=5000)
                    logger.info(f"[LinkedIn Review] Clicked Submit application (attempt {attempt + 1}). Waiting for confirmation...")

                    # Wait up to 8 seconds for success screen
                    for check in range(8):
                        await target.wait_for_timeout(1000)
                        try:
                            next_step = await self.detect_easy_apply_step(target)
                            if next_step == "success":
                                logger.info("[LinkedIn Review] Success screen detected!")
                                job.status = "applied"
                                db.commit()
                                return True
                        except Exception:
                            pass

                    # Even if success screen not detected, assume submitted if no error
                    logger.info("[LinkedIn Review] Submit clicked — assuming success.")
                    job.status = "applied"
                    db.commit()
                    return True

                except Exception as click_err:
                    logger.warning(f"[LinkedIn Review] Submit click attempt {attempt + 1} failed: {click_err}")
                    if attempt < 2:
                        await target.wait_for_timeout(2000)  # Wait before retry
                        # Re-resolve curr_target in case modal context shifted
                        try:
                            _, new_modal = await self.get_active_target(
                                target if hasattr(target, "goto") else target
                            )
                            curr_target = new_modal if new_modal else curr_target
                        except Exception:
                            pass
                    continue
            else:
                logger.warning(f"[LinkedIn Review] Submit button not found on attempt {attempt + 1}.")
                await target.wait_for_timeout(1500)

        logger.warning("[LinkedIn Review] Submit application button not found or not clickable after 3 attempts.")
        return False

    async def is_session_expired(self, page: Page) -> bool:
        return "linkedin.com/login" in page.url or "linkedin.com/authwall" in page.url

    async def dismiss_popups(self, page: Page) -> None:
        for p_sel in [
            "button[aria-label='Dismiss']",
            "button.modal__dismiss",
            ".artdeco-modal__dismiss",
            "button:has-text('Sign in to view more')",
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
        async def _find_apply_btn_js():
            return await page.evaluate_handle(
                """() => {
                    const sels = [
                        'button.jobs-apply-button',
                        'button[aria-label*="Easy Apply"]',
                        'button[aria-label*="easy apply"]',
                        '.jobs-s-apply button',
                        'a.jobs-apply-button',
                    ];
                    for (const s of sels) {
                        const el = document.querySelector(s);
                        if (el && el.offsetParent !== null) return el;
                    }
                    for (const btn of document.querySelectorAll('button, a')) {
                        const t = btn.innerText.trim().toLowerCase();
                        if ((t === 'easy apply' || t === 'apply now') && btn.offsetParent !== null)
                            return btn;
                    }
                    return null;
                }"""
            )

        for scan in range(3):
            h = await _find_apply_btn_js()
            el = h.as_element()
            if el:
                logger.info(f"LinkedIn Easy Apply button found (JS scan {scan + 1}/3)")
                return el
            await page.wait_for_timeout(2000)
            await page.evaluate("window.scrollTo(0, 300)")

        for sel in [
            "button.jobs-apply-button",
            "button[aria-label*='Easy Apply']",
            "button[aria-label*='easy apply']",
            ".jobs-s-apply button",
            "button[data-control-name='jobdetails_topcard_inapply']",
            "a.jobs-apply-button",
            "button:has-text('Easy Apply')",
            "button:has-text('Apply now')",
            "a:has-text('Apply')",
        ]:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    logger.info(f"LinkedIn Easy Apply button found via selector: {sel}")
                    return btn
            except Exception:
                continue

        return None

    async def wait_for_apply_interface(self, page: Page) -> bool:
        combined_selector = ".artdeco-modal, [role='dialog'], .jobs-easy-apply-modal"
        try:
            modal_el = page.locator(combined_selector).first
            await modal_el.wait_for(state="visible", timeout=8000)
            logger.info(f"[LinkedIn Apply] Easy Apply modal detected using: {combined_selector}")
            return True
        except Exception:
            pass
        logger.warning("[LinkedIn Apply] No Easy Apply modal appeared after click. Proceeding blindly.")
        return False

    async def is_external_redirect(self, page: Page, original_domain: str) -> Optional[dict]:
        current_domain = urlparse(page.url).netloc
        if current_domain != original_domain and "linkedin" not in current_domain:
            return {
                "status": "warning",
                "message": "External form detected (Google Form / Company Portal). Complete manually.",
                "url": page.url,
            }
        return None
