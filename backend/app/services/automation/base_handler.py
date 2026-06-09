import logging
from playwright.async_api import Page
from typing import Optional

logger = logging.getLogger(__name__)

class BasePlatformHandler:
    def __init__(self, automation_service):
        """
        Base constructor for all platform-specific handlers.
        :param automation_service: Reference to the orchestrating AutomationService instance.
        """
        self.service = automation_service

    async def _find_first_visible(self, curr_target, selectors: list[str], timeout_ms: int = 1000):
        """
        Iterate through the given selectors, and find the first matching element that is visible and enabled.
        """
        for sel in selectors:
            try:
                locators = curr_target.locator(sel)
                count = await locators.count()
                for i in range(count):
                    btn = locators.nth(i)
                    if await btn.is_visible(timeout=timeout_ms) and await btn.is_enabled():
                        return btn
            except Exception as e:
                logger.debug(f"Error checking visibility for selector '{sel}': {e}")
                continue
        return None

    async def _click_first_visible(self, curr_target, selectors: list[str], timeout_ms: int = 1000) -> bool:
        """
        Locate the first visible and enabled element among selectors, and click it.
        """
        btn = await self._find_first_visible(curr_target, selectors, timeout_ms)
        if btn:
            try:
                await btn.scroll_into_view_if_needed()
                await btn.click()
                logger.info(f"Clicked visible element matching selectors")
                return True
            except Exception as e:
                logger.warning(f"Failed to click matched element: {e}")
        return False


    async def get_active_target(self, page: Page) -> tuple:
        """
        Determine the active target context (Page or Frame) and modal locator.
        Returns: (target, modal_locator)
        """
        raise NotImplementedError

    async def detect_easy_apply_step(self, target) -> str:
        """
        Identify the type of the currently visible apply step (e.g. success, contact_info, questions, etc.).
        """
        raise NotImplementedError

    async def click_next_or_review(self, target) -> bool:
        """
        Locate and click the Next/Continue/Review navigation button inside target.
        """
        raise NotImplementedError

    async def handle_review_step(self, target, modal_locator, db, job) -> bool:
        """
        Handle final review page actions (like unchecking follow check box and clicking submit application).
        Returns: True if application was successfully submitted, False otherwise.
        """
        raise NotImplementedError

    async def is_session_expired(self, page: Page) -> bool:
        """
        Check if the current browser page indicates the user session has expired or requires login.
        """
        raise NotImplementedError

    async def dismiss_popups(self, page: Page) -> None:
        """
        Dismiss platform-specific cookie consent headers, popup modals, or sign-in blocks.
        """
        raise NotImplementedError

    async def find_apply_button(self, page: Page):
        """
        Exhaustively search for the Platform's apply/easy-apply button.
        Returns the Locator/Element if found, else None.
        """
        raise NotImplementedError

    async def wait_for_apply_interface(self, page: Page) -> bool:
        """
        Wait for the platform's application interface (modal, iframe, or redirect) to appear after clicking Apply.
        """
        raise NotImplementedError

    async def is_external_redirect(self, page: Page, original_domain: str) -> Optional[dict]:
        """
        Check if the current page has redirected to an external ATS platform.
        """
        raise NotImplementedError
