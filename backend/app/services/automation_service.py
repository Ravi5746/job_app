import tempfile
import psutil

from dotenv import load_dotenv
import asyncio
import sys
import os
import re
import json
import logging
from typing import Optional
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright, Page, FileChooser, Frame
from sqlalchemy.orm import Session
from app.models.job import Job as JobModel
from app.models.resume import Resume as ResumeModel
from app.ai.hermes import hermes_agent
from app.core.config import settings
from app.core import security
from app.ai import prompts
from app.services.automation.linkedin_handler import LinkedInHandler
from app.services.automation.indeed_handler import IndeedHandler

load_dotenv()

# Fix for NotImplementedError when using Playwright on Windows
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        pass

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def _normalize_questionnaire(questionnaire_data: list) -> dict:
    """Normalize questionnaire data from user settings into a {question: answer} dict."""
    normalized = {}
    if not questionnaire_data:
        return normalized
    for item in questionnaire_data:
        if isinstance(item, dict):
            q = item.get("question", "").strip()
            a = item.get("answer", "").strip()
            if q and a:  # Only include questions that have actual answers
                normalized[q] = a
        elif isinstance(item, str):
            # Default questionnaire format: plain string questions without answers.
            # These are skipped — they become useful only after the user fills
            # them in via the Settings page (which converts them to {question, answer} dicts).
            logger.debug(f"[Questionnaire] Skipping string-only question (no answer): '{item[:60]}'")
    return normalized


class AutomationService:
    def __init__(self):
        self.tinyfish_key = settings.TINYFISH_API_KEY

        # Verify Hermes (Gemini/OpenRouter) client is available
        if not hermes_agent.client:
            logger.warning(
                "Hermes (Gemini) client is not configured (OPENAI_API_KEY missing) "
                "— question answering will be skipped."
            )

        # Base API URL for resume downloads
        self._api_base_url = (
            getattr(settings, "NEXT_PUBLIC_API_URL", "")
            or os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        )

        # Instantiate platform-specific handlers
        self.linkedin_handler = LinkedInHandler(self)
        self.indeed_handler = IndeedHandler(self)
        
        # Instantiate DOM Layer
        from app.services.automation.agent.dom_layer import DOMLayer
        self._dom = DOMLayer()

        # Cache active browser contexts: {(user_id, platform_name): BrowserContext}
        self._playwright = None
        self._active_contexts = {}

    async def _get_playwright(self):
        if not self._playwright:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            logger.info("[Browser] Persistent Playwright process started.")
        return self._playwright

    async def _get_or_create_context(self, user_id: int, platform_name: str):
        key = (user_id, platform_name)
        context = self._active_contexts.get(key)
        
        if context:
            try:
                # Test connection health by accessing pages property
                context.pages
                logger.info(f"[Browser] Reusing active browser context for user {user_id} on {platform_name}")
                return context
            except Exception as e:
                logger.warning(f"[Browser] Cached browser context was unhealthy or closed: {e}. Recreating...")
                self._active_contexts.pop(key, None)
                try:
                    await context.close()
                except Exception:
                    pass

        logger.info(f"[Browser] Launching new persistent context for user {user_id} on {platform_name}")
        pw = await self._get_playwright()
        user_data_dir = os.path.join(settings.USER_DATA_DIR, str(user_id), platform_name)
        os.makedirs(user_data_dir, exist_ok=True)

        # Pre-emptively remove stale Chromium SingletonLock file
        lock_file = os.path.join(user_data_dir, "SingletonLock")
        if os.path.exists(lock_file):
            try:
                logger.info(f"[Browser] Pre-emptively removing stale browser SingletonLock file for user {user_id}")
                os.remove(lock_file)
            except Exception as e:
                logger.warning(f"[Browser] Could not pre-emptively remove browser SingletonLock: {e}")

        for attempt in range(3):
            try:
                context = await pw.chromium.launch_persistent_context(
                    user_data_dir,
                    headless=settings.HEADLESS,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-infobars",
                    ],
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                    ignore_default_args=["--enable-automation"],
                )
                break
            except Exception as exc:
                if attempt == 2:
                    raise
                logger.warning(f"[Browser] Launch attempt failed, retry {attempt + 2}/3: {exc}")
                # Cross-platform process killing using psutil
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'exe']):
                        try:
                            proc_name = (proc.info['name'] or '').lower()
                            if 'chrome' in proc_name or 'chromium' in proc_name:
                                exe_path = (proc.info['exe'] or '').lower()
                                if 'ms-playwright' in exe_path:
                                    logger.info(f"[Browser] Killing orphaned browser process: {proc.info['name']} (PID: {proc.info['pid']})")
                                    proc.kill()
                        except (psutil.NoSuchProcess, proc.AccessDenied):
                            pass
                except Exception as kill_err:
                    logger.warning(f"[Browser] Could not kill orphaned chrome processes: {kill_err}")
                
                if os.path.exists(lock_file):
                    try:
                        os.remove(lock_file)
                    except Exception:
                        pass
                await asyncio.sleep(2)

        self._active_contexts[key] = context
        return context

    # ═══════════════════════════════════════════════════════════════════════
    # PAGE UTILITIES
    # ═══════════════════════════════════════════════════════════════════════

    async def _wait_for_page_settle(self, target, timeout_ms=3000):
        """Wait for the target (Page or Frame) to settle (DOM loaded, loaders/spinners hidden, and settle delay)."""
        try:
            await target.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except Exception:
            pass

        # Wait for any active loaders/spinners to disappear
        for loader_sel in [
            ".artdeco-loader",
            "[class*='loader']",
            "[class*='spinner']",
            ".jobs-easy-apply-modal__spinner",
            ".ia-BasePage-loading",
            "[class*='loading']",
        ]:
            try:
                loader = target.locator(loader_sel).first
                if await loader.is_visible(timeout=400):
                    logger.debug(f"[Settle] Loader '{loader_sel}' visible, waiting for it to hide...")
                    await loader.wait_for(state="hidden", timeout=8000)
            except Exception:
                pass

        await target.wait_for_timeout(1000)

    async def _find_indeed_frame(self, page: Page) -> Optional[Frame]:
        """Find the Indeed apply iframe if present, otherwise return None."""
        for frame in page.frames:
            url = frame.url.lower()
            name = frame.name.lower()
            if "indeedapply" in url or "indeedapply" in name or "indeed-apply" in url:
                return frame
        return None

    async def _get_active_modal(self, target):
        """Delegates modal container location to the DOMLayer class."""
        return await self._dom.get_active_modal(target)



    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 0 — Pre-download resume from the API
    # ═══════════════════════════════════════════════════════════════════════

    async def _download_resume_to_temp(self, resume_id: int, user_id: int) -> Optional[str]:
        """GET /api/v1/resumes/{id}/download and persist to a temp file."""
        if not resume_id:
            return None

        base = self._api_base_url.rstrip("/")
        if "/api/v1" not in base:
            base += "/api/v1"
        url = f"{base}/resumes/{resume_id}/download"

        try:
            token = security.create_access_token(user_id)
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
                resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            disposition  = resp.headers.get("content-disposition", "")
            ext = (
                ".pdf"  if "pdf"  in content_type or ".pdf"  in disposition else
                ".docx" if "docx" in content_type or ".docx" in disposition else
                ".pdf"
            )
            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix=ext, prefix=f"resume_{resume_id}_"
            )
            tmp.write(resp.content)
            tmp.close()
            logger.info(f"[Resume] Downloaded → {tmp.name} ({len(resp.content):,} bytes)")
            return tmp.name
        except Exception as exc:
            logger.error(f"[Resume] Download failed: {exc}")
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # STEP DETECTOR
    # ═══════════════════════════════════════════════════════════════════════





    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 3 — Resume upload
    # ═══════════════════════════════════════════════════════════════════════

    async def _handle_resume_upload(self, target, resume_file_path: Optional[str]) -> None:
        modal_locator = await self._get_active_modal(target)
        curr_target = modal_locator if modal_locator else target

        # Check if a resume is already selected/active in the modal
        try:
            selected_indicators = [
                ".jobs-document-upload-redesign-card__container--active",
                "[class*='card--active']",
                "[class*='card__container--active']",
                "input[type='radio'][checked]",
                "[aria-checked='true']",
                "[class*='resume-uploaded']",
                "[class*='upload-success']",
                ".ia-Resume-alreadyUploaded",
            ]
            for sel in selected_indicators:
                if await curr_target.locator(sel).count() > 0:
                    el = curr_target.locator(sel).first
                    if await el.is_visible(timeout=1000):
                        logger.info(f"[ResumeUpload] Resume already selected via: {sel}. Skipping upload.")
                        return

            # Fallback text check: if modal text indicates a resume is selected
            modal_text = (await curr_target.inner_text()).lower()
            if "selected" in modal_text and any(ext in modal_text for ext in [".pdf", ".docx", ".doc"]):
                logger.info("[ResumeUpload] Resume appears pre-selected in modal. Skipping upload.")
                return
        except Exception as exc:
            logger.debug(f"[ResumeUpload] Error checking pre-selected resume status: {exc}")

        if not resume_file_path or not os.path.exists(resume_file_path):
            logger.warning("[ResumeUpload] No local file available — skipping.")
            return

        logger.info(f"[ResumeUpload] Uploading: {resume_file_path}")

        # Strategy A: direct hidden <input type="file">
        for sel in [
            "input[type='file']",
            "input[accept*='pdf']",
            "input[accept*='.pdf,.doc,.docx']",
            "input[name='resume']",
            "input[name='file']",
        ]:
            try:
                el = curr_target.locator(sel).first
                if await el.count() > 0:
                    await el.set_input_files(resume_file_path)
                    logger.info("[ResumeUpload] ✓ Via direct file-input.")
                    await target.wait_for_timeout(2500)
                    return
            except Exception as exc:
                logger.debug(f"[ResumeUpload] Strategy A ({sel}): {exc}")

        # Strategy B: click upload button → intercept OS file chooser
        for sel in [
            "button:has-text('Upload resume')",
            "button:has-text('Upload')",
            "label:has-text('Upload resume')",
            ".jobs-document-upload-redesign-card__container button",
            "[data-test-resume-upload-btn]",
            "[data-testid='resume-upload']",
            ".file-upload-input",
        ]:
            try:
                btn = curr_target.locator(sel).first
                if not await btn.is_visible(timeout=2000):
                    continue
                # Safely get page object (Page or Frame context)
                page_obj = target if hasattr(target, "context") else target.page
                async with page_obj.expect_file_chooser(timeout=5000) as fc_ctx:
                    await btn.click()
                fc: FileChooser = await fc_ctx.value
                await fc.set_files(resume_file_path)
                logger.info("[ResumeUpload] ✓ Via file-chooser.")
                await target.wait_for_timeout(3000)
                return
            except Exception as exc:
                logger.debug(f"[ResumeUpload] Strategy B ({sel}): {exc}")

        logger.warning("[ResumeUpload] ✗ No upload mechanism found.")

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 3 — Robust field filling (data-qa-idx primary strategy)
    # ═══════════════════════════════════════════════════════════════════════

    async def _fill_field_robust(self, target, field_answer: dict) -> bool:
        """
        Fill a single form field using React-compatible Playwright interactions.
        Uses a hierarchical locator strategy: data-qa-idx → CSS selector → label → id/name.
        """
        qa_idx   = str(field_answer.get("qa_idx")    or "").strip()
        ftype    = str(field_answer.get("type")       or "text").strip()
        answer   = str(field_answer.get("answer")     or "").strip()
        label    = str(field_answer.get("label")      or "").strip()
        selector = str(field_answer.get("selector")   or "").strip()

        if not answer and ftype != "checkbox":
            return False

        modal_locator = await self._get_active_modal(target)
        curr_target = modal_locator if modal_locator else target

        # ── Inner fill helpers ─────────────────────────────────────────────

        async def fill_text(el) -> bool:
            """React-compatible text fill: clear, fill and dispatch events."""
            try:
                await el.scroll_into_view_if_needed()
                await el.click(timeout=1500)
                await target.wait_for_timeout(80)
                await el.press("Control+a")
                await el.press("Delete")
                await el.fill(answer)
                await el.evaluate(
                    "el => { "
                    "el.dispatchEvent(new Event('input', { bubbles: true })); "
                    "el.dispatchEvent(new Event('change', { bubbles: true })); "
                    "}"
                )
                await target.wait_for_timeout(100)
                logger.debug(f"[Fill] Text field '{label or qa_idx}' filled with '{answer}'")
                return True
            except Exception as exc:
                logger.debug(f"[Fill] fill_text error: {exc}")
                return False

        async def fill_select(el) -> bool:
            """Select option: exact label → exact value → partial text match."""
            for fn in [
                lambda: el.select_option(label=answer, timeout=1500),
                lambda: el.select_option(value=answer, timeout=1500),
            ]:
                try:
                    await fn()
                    await target.wait_for_timeout(100)
                    return True
                except Exception:
                    pass
            # Partial match fallback
            try:
                opts = await el.evaluate(
                    "el => Array.from(el.options).map(o => ({v: o.value, t: o.text.trim()}))"
                )
                for opt in opts:
                    if answer.lower() in opt["t"].lower():
                        await el.select_option(value=opt["v"])
                        await target.wait_for_timeout(100)
                        return True
            except Exception as exc:
                logger.debug(f"[Fill] fill_select partial error: {exc}")
            return False

        async def fill_radio(el) -> bool:
            """Click radio button element, with fallback for covered/styled elements."""
            try:
                await el.scroll_into_view_if_needed()
                try:
                    await el.click(timeout=1000)
                except Exception:
                    await el.click(force=True, timeout=1000)
                await target.wait_for_timeout(100)
                logger.debug(f"[Fill] Radio button clicked successfully")
                return True
            except Exception as exc:
                logger.debug(f"[Fill] fill_radio direct click error: {exc}")

            # Fallback: click associated <label for="id">
            try:
                fid = await el.get_attribute("id")
                if fid:
                    lbl = curr_target.locator(f'label[for="{fid}"]').first
                    if await lbl.count() > 0:
                        await lbl.click(force=True, timeout=1000)
                        await target.wait_for_timeout(100)
                        logger.debug(f"[Fill] Radio clicked via label[for='{fid}'] fallback")
                        return True
            except Exception as exc:
                logger.debug(f"[Fill] fill_radio label[for] fallback error: {exc}")

            # Fallback 2: click label matching the answer text
            try:
                safe = answer.replace("'", "\\'")
                lbl = curr_target.locator(f"label:has-text('{safe}')").first
                if await lbl.count() > 0:
                    await lbl.click(force=True, timeout=1000)
                    await target.wait_for_timeout(100)
                    logger.debug(f"[Fill] Radio clicked via label:has-text('{answer}') fallback")
                    return True
            except Exception as exc:
                logger.debug(f"[Fill] fill_radio text fallback error: {exc}")
            return False

        async def fill_checkbox(el) -> bool:
            """Check or uncheck checkbox element, with label fallbacks."""
            try:
                await el.scroll_into_view_if_needed()
                is_checked = await el.is_checked()
                target_state = answer.lower() in ("yes", "true", "checked", "1", "on")
                if is_checked != target_state:
                    try:
                        await el.click(timeout=1000)
                    except Exception:
                        await el.click(force=True, timeout=1000)
                    await target.wait_for_timeout(100)
                logger.debug(f"[Fill] Checkbox state set to {target_state}")
                return True
            except Exception as exc:
                logger.debug(f"[Fill] fill_checkbox error: {exc}")

            # Fallback: click parent or sibling label
            try:
                fid = await el.get_attribute("id")
                if fid:
                    lbl = curr_target.locator(f'label[for="{fid}"]').first
                    if await lbl.count() > 0:
                        await lbl.click(force=True, timeout=1000)
                        await target.wait_for_timeout(100)
                        return True
            except Exception as exc:
                logger.debug(f"[Fill] fill_checkbox label fallback error: {exc}")
            return False

        # ── Resolve element locator ────────────────────────────────────────

        el = None

        # 1. Primary: data-qa-idx attribute
        if qa_idx:
            try:
                candidate = target.locator(f'[data-qa-idx="{qa_idx}"]').first
                if await candidate.count() > 0 and await candidate.is_visible(timeout=1000):
                    el = candidate
                    logger.info(f"[Fill] Located field '{label or ftype}' using data-qa-idx='{qa_idx}'")
            except Exception as exc:
                logger.debug(f"[Fill] data-qa-idx lookup error: {exc}")

        # 2. Secondary: CSS selector fallback
        if el is None and selector:
            try:
                candidate = target.locator(selector).first
                if await candidate.count() > 0 and await candidate.is_visible(timeout=1000):
                    el = candidate
                    logger.info(f"[Fill] Located field using CSS selector fallback: '{selector}'")
            except Exception as exc:
                logger.debug(f"[Fill] Selector lookup error: {exc}")

        # 3. Tertiary: Label text
        if el is None and label:
            try:
                candidate = target.get_by_label(label).first
                if await candidate.count() > 0 and await candidate.is_visible(timeout=1000):
                    el = candidate
                    logger.info(f"[Fill] Located field using label fallback: '{label}'")
            except Exception as exc:
                logger.debug(f"[Fill] Label lookup error: {exc}")

        # 4. Quaternary: ID or Name extracted from selector string
        if el is None:
            m_id   = re.search(r'#([a-zA-Z0-9_-]+)', selector)
            m_name = re.search(r"name=[\"']?([a-zA-Z0-9_-]+)[\"']?", selector)
            fid    = m_id.group(1)   if m_id   else None
            fname  = m_name.group(1) if m_name else None

            if fid:
                try:
                    candidate = target.locator(f'[id="{fid}"]').first
                    if await candidate.count() > 0 and await candidate.is_visible(timeout=1000):
                        el = candidate
                        logger.info(f"[Fill] Located field using ID: '{fid}'")
                except Exception:
                    pass

            if el is None and fname:
                try:
                    candidate = target.locator(f'[name="{fname}"]').first
                    if await candidate.count() > 0 and await candidate.is_visible(timeout=1000):
                        el = candidate
                        logger.info(f"[Fill] Located field using name: '{fname}'")
                except Exception:
                    pass

        # ── Dispatch to fill helper ────────────────────────────────────────

        if el is None:
            logger.warning(
                f"[Fill] ✗ Could not locate element: "
                f"qa_idx={qa_idx}, selector={selector}, label={label}"
            )
            return False

        is_text = ftype in ("text", "number", "textarea")
        if is_text:
            return await fill_text(el)
        elif ftype == "select":
            return await fill_select(el)
        elif ftype == "checkbox":
            return await fill_checkbox(el)
        else:
            return await fill_radio(el)

    # ═══════════════════════════════════════════════════════════════════════
    # Navigation helper
    # ═══════════════════════════════════════════════════════════════════════



    # ═══════════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT
    # ═══════════════════════════════════════════════════════════════════════

    async def apply_to_job(self, db: Session, job_id: int, user_id: int):
        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if not job:
            return {"status": "error", "message": "Critical: Job record not found in database."}
        if job.status == "applied":
            return {"status": "error", "message": "Already applied: job is already marked 'applied'."}

        resume = (
            db.query(ResumeModel)
            .filter(ResumeModel.user_id == user_id)
            .order_by(ResumeModel.created_at.desc())
            .first()
        )

        profile_data: dict = {}
        resume_text: str = ""
        if resume:
            resume_text = resume.content or ""

        # Load enriched profile from the User table (stored during resume upload).
        # This avoids a redundant AI extraction call on every apply.
        from app.models.user import User as UserModel
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if user:
            profile_data = {
                "full_name":              user.full_name or "",
                "email":                  user.email or "",
                "phone":                  user.phone or "",
                "phone_country_code":     user.phone_country_code or "",
                "location":               user.location or "",
                "linkedin_url":           user.linkedin_url or "",
                "github_url":             user.github_url or "",
                "portfolio_url":          user.portfolio_url or "",
                "summary":                user.summary or "",
                "skills":                 user.skills or [],
                "work_experience":        user.work_experience or [],
                "total_years_experience": user.total_years_experience or 0,
                "education":              user.education or [],
                "certifications":         user.certifications or [],
                "languages":              user.languages or [],
                "expected_salary":        user.expected_salary or "",
                "notice_period":          user.notice_period or "",
                "work_authorization":     user.work_authorization or "",
                "willing_to_relocate":    user.willing_to_relocate,
                "desired_job_titles":     user.desired_job_titles or [],
                "questionnaire_answers":  _normalize_questionnaire(user.questionnaire),
            }
            logger.info(
                f"Loaded enriched profile for: {profile_data.get('full_name', 'User')} "
                f"({len(profile_data.get('skills', []))} skills stored)"
            )

        # Fallback: if no enriched data exists, extract from resume on-the-fly
        if not profile_data.get("full_name") and resume:
            logger.info("No stored profile found, extracting from resume...")
            profile_data = await hermes_agent.extract_profile_data(resume.content)
            await hermes_agent.store_user_profile(db, user_id, profile_data)
            logger.info(f"Profile extracted and stored for: {profile_data.get('full_name', 'User')}")

            # Reload from DB to ensure questionnaire answers are populated
            user = db.query(UserModel).filter(UserModel.id == user_id).first()
            if user:
                profile_data["questionnaire_answers"] = _normalize_questionnaire(user.questionnaire)
                profile_data["desired_job_titles"]    = user.desired_job_titles or []

        # Normalise job URL
        if not job.url.startswith("http"):
            if job.source and "indeed" in job.source.lower():
                job.url = f"https://www.indeed.com{'/' + job.url.lstrip('/')}"
            else:
                job.url = f"https://www.linkedin.com{'/' + job.url.lstrip('/')}"

        is_indeed = "indeed.com" in job.url.lower()

        # Pre-download resume file before launching the browser
        resume_file_path: Optional[str] = None
        if resume and getattr(resume, "id", None):
            resume_file_path = await self._download_resume_to_temp(resume.id, user_id=user_id)
            if not resume_file_path:
                logger.warning("Resume download failed — proceeding without file upload.")

        logger.info(f"Starting auto-apply: {job.title} @ {job.company}")

        platform_name = "indeed" if is_indeed else "linkedin"
        context = None
        page = None
        try:
            context = await self._get_or_create_context(user_id, platform_name)
            page = await context.new_page()

            # Anti-detection script
            await page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                """
            )

            # Resolve job URL (convert search/collection URLs to direct job view)
            target_url = job.url
            if not is_indeed and "linkedin.com/jobs/search" in target_url.lower():
                m = re.search(r"currentJobId=(\d+)", target_url)
                if m:
                    target_url = f"https://www.linkedin.com/jobs/view/{m.group(1)}/"

            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as nav_err:
                logger.warning(f"Navigation soft-failed: {nav_err}")

            await page.wait_for_timeout(4000)
            await page.evaluate("window.scrollTo(0, 400)")
            await page.wait_for_timeout(1000)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(1000)

            # If on a LinkedIn search/collection page, click the first job card
            if not is_indeed and ("jobs/search" in page.url or "jobs/collections" in page.url):
                for s_sel in [
                    ".job-card-container",
                    ".jobs-search-results__list-item",
                    ".jobs-search-results-list__item",
                ]:
                    try:
                        item = page.locator(s_sel).first
                        if await item.is_visible(timeout=3000):
                            await item.click()
                            await page.wait_for_timeout(3000)
                            break
                    except Exception:
                        continue

            # Get platform-specific handler
            handler = self.indeed_handler if is_indeed else self.linkedin_handler

            # Dismiss popups / sign-in walls / cookie consent banners
            await handler.dismiss_popups(page)

            # Guard: Cloudflare or login wall
            page_content = await page.content()
            if "Request Blocked" in page_content or "Cloudflare" in page_content:
                return {"status": "error", "message": "Blocked by Cloudflare. Log in manually first."}
            
            # Wait for Cloudflare/Turnstile challenges to be solved (up to 50 seconds in headed browser)
            for captcha_check in range(5):
                page_content = await page.content()
                if any(kw in page_content.lower() for kw in ["security check", "verify you are human", "hcaptcha", "turnstile"]):
                    logger.warning("[Apply] Security check / Captcha detected! Waiting 10s for manual resolution in browser...")
                    await page.wait_for_timeout(10000)
                else:
                    break

            # Check if session has expired
            if await handler.is_session_expired(page):
                platform_name_cap = "Indeed" if is_indeed else "LinkedIn"
                return {"status": "error", "message": f"{platform_name_cap} session expired. Reconnect in Settings."}

            # ── Locate Easy Apply button ──────────────────────────────────
            apply_button = await handler.find_apply_button(page)

            if not apply_button:
                return {
                    "status": "error",
                    "message": "Easy Apply button not found after exhaustive search.",
                }

            # Check if the button text indicates an external redirect (Indeed specific)
            if is_indeed:
                btn_text = ""
                try:
                    btn_text = (await apply_button.inner_text()).lower()
                except Exception:
                    pass
                if "company site" in btn_text or "employer" in btn_text:
                    return {
                        "status": "warning",
                        "message": "External application (Company website) detected. Complete manually.",
                        "url": job.url,
                    }

            original_domain = urlparse(page.url).netloc
            
            # Click apply button and handle new tab contexts
            new_page = None
            try:
                async with page.context.expect_page(timeout=4000) as new_page_info:
                    try:
                        await apply_button.click()
                    except Exception:
                        await page.evaluate("el => el.click()", apply_button)
                new_page = await new_page_info.value
                logger.info("[Apply] Application opened in a new tab.")
            except Exception as e:
                logger.info(f"[Apply] No new tab opened (Reason: {type(e).__name__}). Checking redirect or modal...")

            if new_page:
                page = new_page
                await self._wait_for_page_settle(page)
            else:
                await self._wait_for_page_settle(page)

            # Wait for platform-specific application interface to appear
            await handler.wait_for_apply_interface(page)
            await self._wait_for_page_settle(page)

            # ── Set resume path for ToolRegistry ──────────────────────────
            self._resume_path = resume_file_path

            # ── Instantiate agent components ──────────────────────────────
            from app.ai.agent_llm import create_llm
            from app.services.automation.agent.tool_registry import ToolRegistry
            from app.services.automation.agent.application_agent import ApplicationAgent

            llm = create_llm("smart")
            tools = ToolRegistry(self._dom, self)
            agent = ApplicationAgent(
                llm=llm,
                dom=self._dom,
                tools=tools,
                profile=profile_data,
                resume_text=resume_text,
                job_id=job_id,
                user_id=user_id,
            )

            # ── Main step loop ────────────────────────────────────────────
            MAX_STEPS = settings.MAX_FORM_STEPS
            for step_num in range(1, MAX_STEPS + 1):
                # Resolve active target context (Page or Frame) and form locator
                target, modal_locator = await handler.get_active_target(page)
                await self._wait_for_page_settle(target)

                step_type = await handler.detect_easy_apply_step(target)
                logger.info(f"━━ Step {step_num}/{MAX_STEPS}: [{step_type.upper()}] ━━")

                if step_type == "success" or agent._state.phase.name == "SUCCESS":
                    job.status = "applied"
                    db.commit()
                    break

                # Delegate core form filling and navigation to ApplicationAgent
                result = await agent.run_step(target, step_num)
                status = result.get("status")

                if status == "success":
                    job.status = "applied"
                    db.commit()
                    break
                elif status == "blocked":
                    logger.warning(f"Application blocked: {result.get('reason')}")
                    break
                elif status == "error":
                    logger.error(f"Application error: {result.get('message')}")
                    break

                # If review step and agent completed filling, check if we should review
                if step_type == "review":
                    submitted = await handler.handle_review_step(target, modal_locator, db, job)
                    if submitted:
                        break

            # ── External redirect detection ───────────────────────────────
            redirect_warning = await handler.is_external_redirect(page, original_domain)
            if redirect_warning:
                return redirect_warning

            is_success = (job.status == "applied")

            os.makedirs(settings.SCREENSHOTS_DIR, exist_ok=True)
            screenshot_path = os.path.join(settings.SCREENSHOTS_DIR, f"job_{job_id}_applied.png")
            await page.screenshot(path=screenshot_path, full_page=True)
            await page.wait_for_timeout(5000)

            return {
                "status": "success" if is_success else "partial",
                "message": (
                    "Application submitted and verified!"
                    if is_success
                    else "Automation complete — verify result in browser."
                ),
                "screenshot": screenshot_path,
            }

        except Exception as exc:
            logger.exception(f"Automation Error: {exc}")
            return {"status": "error", "message": f"Automation Error: {exc}"}

        finally:
            try:
                if page:
                    await page.close()
            except Exception:
                pass
            # Clean up temp resume file
            if resume_file_path and os.path.exists(resume_file_path):
                try:
                    os.remove(resume_file_path)
                except Exception:
                    pass

    # ═══════════════════════════════════════════════════════════════════════
    # LOGIN BROWSER — used by Settings → Connect Platform
    # ═══════════════════════════════════════════════════════════════════════

    async def launch_login_browser(self, platform: str, user_id: int) -> None:
        """
        Open a persistent Chromium browser to the platform's login page.

        This is a lightweight flow — no automation, no form-filling. The user
        manually logs in; Playwright persists cookies/localStorage in the user's
        `browser_data/` directory so that `apply_to_job` can reuse the
        authenticated session later.

        After the user closes the browser (or after a 5-minute timeout), a marker
        file `connected_<platform>.txt` is written so the frontend can show the
        "Connected" status.
        """
        platform_urls = {
            "linkedin":  "https://www.linkedin.com/login",
            "indeed":    "https://www.indeed.com/auth",
            "naukri":    "https://www.naukri.com/nlogin/login",
            "glassdoor": "https://www.glassdoor.com/profile/login_input.htm",
        }

        url = platform_urls.get(platform.lower())
        if not url:
            logger.warning(f"[LoginBrowser] Unknown platform: {platform}")
            return

        # Close any active cached automation context first to release the lock
        key = (user_id, platform.lower())
        cached_context = self._active_contexts.pop(key, None)
        if cached_context:
            try:
                await cached_context.close()
                logger.info(f"[LoginBrowser] Closed active cached context for user {user_id} on {platform}")
            except Exception as e:
                logger.warning(f"[LoginBrowser] Error closing cached context: {e}")

        logger.info(f"[LoginBrowser] Launching browser for user {user_id} on {platform} → {url}")
        context = None
        try:
            pw = await self._get_playwright()
            user_data_dir = os.path.join(settings.USER_DATA_DIR, str(user_id), platform.lower())
            os.makedirs(user_data_dir, exist_ok=True)

            # Pre-emptively remove stale Chromium SingletonLock file
            lock_file = os.path.join(user_data_dir, "SingletonLock")
            if os.path.exists(lock_file):
                try:
                    logger.info("Pre-emptively removing stale browser SingletonLock file in login browser")
                    os.remove(lock_file)
                except Exception as e:
                    logger.warning(f"Could not pre-emptively remove browser SingletonLock in login browser: {e}")

            context = await pw.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                ],
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                ignore_default_args=["--enable-automation"],
            )

            page = context.pages[0] if context.pages else await context.new_page()

            # Anti-detection
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
            """)

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            logger.info(f"[LoginBrowser] Page loaded. Waiting for user to log in…")

            # Wait up to 5 minutes for the user to log in.
            # Detect success by checking if the URL changed away from the login page.
            login_keywords = ["login", "signin", "sign-in", "auth", "nlogin"]
            for _ in range(60):  # 60 × 5s = 5 minutes
                await page.wait_for_timeout(5000)
                current_url = page.url.lower()
                if not any(kw in current_url for kw in login_keywords):
                    logger.info(f"[LoginBrowser] Login detected — URL: {page.url}")
                    break
            else:
                logger.warning(f"[LoginBrowser] Timed out waiting for login on {platform}.")

            # Extract user display name if possible (for connected status label)
            display_name = platform.capitalize()
            try:
                if platform == "linkedin":
                    name_el = page.locator(
                        ".feed-identity-module__actor-meta a, .global-nav__me-photo"
                    ).first
                    if await name_el.count() > 0:
                        display_name = (
                            await name_el.get_attribute("alt") or ""
                        ).strip() or display_name
            except Exception:
                pass

            # Write marker file so /settings/status can report "Connected"
            marker_path = os.path.join(user_data_dir, f"connected_{platform.lower()}.txt")
            with open(marker_path, "w") as f:
                f.write(display_name)
            logger.info(f"[LoginBrowser] Marker written → {marker_path}")

            # Give the user a moment, then close
            await page.wait_for_timeout(2000)

        except Exception as exc:
            logger.error(f"[LoginBrowser] Error: {exc}")
        finally:
            try:
                if context:
                    await context.close()
            except Exception:
                pass


automation_service = AutomationService()