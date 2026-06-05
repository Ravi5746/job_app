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
        """Locate the active, visible modal container in the target (Page or Frame)."""
        logger.info("[GetActiveModal] Starting search for active modal...")
        
        is_frame = hasattr(target, "page")
        selectors = [
            ".jobs-easy-apply-modal",
            ".artdeco-modal",
            "[role='dialog']",
            "div[role='region'][aria-label*='progress']",
            "div[role='region'][aria-label*='application']",
        ]
        if is_frame:
            selectors.extend(["form", "body"])

        for m_sel in selectors:
            try:
                locators = target.locator(f"{m_sel}:visible")
                count = await locators.count()
                logger.info(f"[GetActiveModal] Selector '{m_sel}': found {count} visible element(s)")
                for i in range(count):
                    loc = locators.nth(i)
                    box = await loc.bounding_box()
                    logger.info(f"[GetActiveModal]   Element {i}: BoundingBox={box}")
                    
                    is_linkedin = "linkedin.com" in target.url.lower()
                    if is_linkedin and m_sel != ".jobs-easy-apply-modal":
                        signature_sel = (
                            "progress, [role='progressbar'], [class*='easy-apply'], "
                            ".artdeco-completeness-meter-linear, .jobs-easy-apply-footer__info, "
                            "[data-easy-apply-next-button], .jobs-easy-apply-form-section__grouping"
                        )
                        sig_count = await loc.locator(signature_sel).count()
                        logger.info(
                            f"[GetActiveModal]   Element {i} checking signatures: "
                            f"count={sig_count} (selector: '{signature_sel}')"
                        )
                        if sig_count == 0:
                            logger.info(f"[GetActiveModal]   Element {i} rejected (no signature matches)")
                            continue
                    logger.info(f"[GetActiveModal] Match found! Selector: '{m_sel}', index: {i}")
                    return loc
            except Exception as e:
                logger.warning(f"[GetActiveModal] Selector '{m_sel}' check failed: {e}")
                continue
        logger.info("[GetActiveModal] No active modal found.")
        return None

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 1 — Dynamic HTML Tagging & Minification
    # ═══════════════════════════════════════════════════════════════════════

    async def _clean_and_tag_modal_html(self, target) -> str:
        """
        Uses the Python-validated modal locator from _get_active_modal, then tags
        and minifies its HTML via element-scoped JS evaluation.

        Playwright passes the actual modal DOM element as the first argument to the
        JS function, so we never need to re-search for the modal inside JavaScript.
        This eliminates the race condition where the in-JS isVisible() walk could
        fail on elements that Playwright's own :visible selector already confirmed.
        """
        logger.info("[Scraper] Starting HTML tagging and cleaning...")

        # Re-use the Python-validated locator — no redundant JS modal search needed
        modal_locator = await self._get_active_modal(target)
        if not modal_locator:
            logger.warning("[Scraper] No active modal found — cannot extract HTML.")
            return ""

        try:
            html = await modal_locator.evaluate(
                """(modal) => {
                    // `modal` is the real DOM element handed in by Playwright.
                    // No need to search for the modal — we already have it.

                    function isVisible(el) {
                        if (!el) return false;
                        if (el.type === 'hidden') return false;
                        let curr = el;
                        while (curr && curr !== document.body) {
                            const style = window.getComputedStyle(curr);
                            if (style.display === 'none' || style.visibility === 'hidden') return false;
                            curr = curr.parentElement;
                        }
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 && rect.height === 0) return false;
                        return true;
                    }

                    // Tag all interactive fields in the live modal with sequential data-qa-idx
                    const interactiveSelectors = [
                        "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='file'])",
                        "textarea",
                        "select"
                    ].join(",");
                    const interactiveElements = Array.from(modal.querySelectorAll(interactiveSelectors));

                    let idx = 1;
                    interactiveElements.forEach(el => {
                        if (isVisible(el)) {
                            el.setAttribute('data-qa-idx', String(idx));
                            idx++;
                        } else {
                            el.removeAttribute('data-qa-idx');
                        }
                    });
                    console.log("[JS Scraper] Tagged " + (idx - 1) + " interactive elements.");

                    // Clone the modal to clean it without affecting the live UI
                    const clone = modal.cloneNode(true);

                    const tagsToKeep = new Set([
                        "FORM", "FIELDSET", "LEGEND", "LABEL", "INPUT",
                        "TEXTAREA", "SELECT", "OPTION", "DIV", "SPAN",
                        "P", "H1", "H2", "H3", "H4", "H5", "H6"
                    ]);
                    const attrsToKeep = new Set([
                        "id", "name", "type", "value", "placeholder",
                        "checked", "selected", "required", "aria-label",
                        "aria-labelledby", "for", "data-qa-idx"
                    ]);

                    function cleanNode(node) {
                        if (!node) return;

                        if (node.nodeType !== Node.ELEMENT_NODE) {
                            if (node.nodeType === Node.TEXT_NODE) {
                                const text = node.nodeValue.trim();
                                if (!text) {
                                    node.parentNode && node.parentNode.removeChild(node);
                                } else {
                                    node.nodeValue = text;
                                }
                            }
                            return;
                        }

                        if (!tagsToKeep.has(node.tagName)) {
                            node.parentNode && node.parentNode.removeChild(node);
                            return;
                        }

                        const styleAttr = node.getAttribute('style') || '';
                        if (
                            node.getAttribute('type') === 'hidden' ||
                            styleAttr.includes('display: none') ||
                            styleAttr.includes('visibility: hidden') ||
                            node.hasAttribute('hidden')
                        ) {
                            node.parentNode && node.parentNode.removeChild(node);
                            return;
                        }

                        const attrs = Array.from(node.attributes);
                        attrs.forEach(attr => {
                            if (!attrsToKeep.has(attr.name.toLowerCase())) {
                                node.removeAttribute(attr.name);
                            }
                        });

                        const children = Array.from(node.childNodes);
                        children.forEach(cleanNode);

                        const containerTags = ["DIV", "SPAN", "P"];
                        if (containerTags.includes(node.tagName)) {
                            const hasChildren = node.childNodes.length > 0;
                            const hasText = node.textContent.trim().length > 0;
                            if (!hasChildren && !hasText) {
                                node.parentNode && node.parentNode.removeChild(node);
                            }
                        }
                    }

                    Array.from(clone.childNodes).forEach(cleanNode);

                    const cloneAttrs = Array.from(clone.attributes);
                    cloneAttrs.forEach(attr => {
                        if (!attrsToKeep.has(attr.name.toLowerCase())) {
                            clone.removeAttribute(attr.name);
                        }
                    });

                    return clone.outerHTML;
                }"""
            )
            if not html:
                logger.warning("[Scraper] JS evaluation returned empty string.")
                return ""
            logger.info(f"[Scraper] Extracted {len(html):,} chars of modal HTML.")
            return html
        except Exception as e:
            logger.error(f"[Scraper] Error during HTML clean and tag: {e}")
            return ""

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 2 — Single-Pass LLM Answer Generator
    # ═══════════════════════════════════════════════════════════════════════

    async def _get_single_pass_answers(
        self,
        html_content: str,
        profile_data: dict,
        resume_text: str,
    ) -> list[dict]:
        """
        Send the minified, tagged HTML along with the user's profile and resume
        to Gemini Flash in a single pass to identify all form fields, map them to
        their data-qa-idx values, generate accurate answers, and provide CSS selector fallbacks.
        Returns a list of answer dicts, each containing qa_idx, label, type, answer, selector.
        """
        if not hermes_agent.client:
            logger.warning("[AI] Hermes (Gemini) client not configured — skipping single-pass AI answering.")
            return []
        if not html_content:
            return []

        system_msg = prompts.SINGLE_PASS_FORM_SYSTEM_MSG

        user_msg = prompts.get_single_pass_answers_user_msg(resume_text, profile_data, html_content)

        try:
            resp = await hermes_agent.client.chat.completions.create(
                model=hermes_agent.model_name,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": user_msg},
                ],
                response_format={"type": "json_object"},
                max_tokens=1000,
                temperature=0.1,
            )
            raw = resp.choices[0].message.content.strip()
            # Strip any markdown fences the model may have added
            raw = re.sub(r"^```(?:json)?\s*|```$", "", raw, flags=re.MULTILINE).strip()

            parsed_data = json.loads(raw)
            if isinstance(parsed_data, dict):
                answers = parsed_data.get("answers", [])
            elif isinstance(parsed_data, list):
                answers = parsed_data
            else:
                answers = []

            logger.info(f"[AI] Received {len(answers)} answer(s) from single-pass AI: {answers}")
            return answers
        except json.JSONDecodeError as exc:
            logger.error(f"[AI] JSON parse error: {exc} | snippet: {raw[:400]}")
            return []
        except Exception as exc:
            logger.error(f"[AI] Gemini Flash single-pass call failed: {exc}")
            return []

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
    # PHASE 2 — Fill contact info
    # ═══════════════════════════════════════════════════════════════════════

    async def _fill_contact_info(self, target, user_data: dict) -> None:
        logger.info("[ContactInfo] Filling contact details…")
        email    = user_data.get("email", "")
        phone_cc = user_data.get("phone_country_code", "India (+91)")
        phone    = user_data.get("phone_number") or user_data.get("phone") or ""
        full_name = user_data.get("full_name", "")

        modal_locator = await self._get_active_modal(target)
        curr_target = modal_locator if modal_locator else target

        # Fill names if visible (Indeed style)
        if full_name:
            names = full_name.split(maxsplit=1)
            first_name = names[0]
            last_name = names[1] if len(names) > 1 else ""
            
            for sel in ["input[name*='firstName']", "input[name*='first_name']", "input[id*='firstName']"]:
                try:
                    el = curr_target.locator(sel).first
                    if await el.is_visible(timeout=1000):
                        if not await el.input_value() and first_name:
                            await el.fill(first_name)
                        break
                except Exception:
                    continue
            for sel in ["input[name*='lastName']", "input[name*='last_name']", "input[id*='lastName']"]:
                try:
                    el = curr_target.locator(sel).first
                    if await el.is_visible(timeout=1000):
                        if not await el.input_value() and last_name:
                            await el.fill(last_name)
                        break
                except Exception:
                    continue

        for sel in ["input[id*='email']", "input[name*='email']", "input[type='email']"]:
            try:
                el = curr_target.locator(sel).first
                if await el.is_visible(timeout=1500):
                    if not await el.input_value() and email:
                        await el.fill(email)
                    break
            except Exception:
                continue

        for sel in [
            "select[id*='phoneCountryCode']",
            "select[name*='countryCode']",
            ".fb-dropdown select",
        ]:
            try:
                el = curr_target.locator(sel).first
                if await el.is_visible(timeout=1500) and phone_cc:
                    await el.select_option(label=phone_cc)
                    await target.wait_for_timeout(300)
                    break
            except Exception:
                continue

        for sel in [
            "input[id*='phoneNumber']",
            "input[name*='phoneNumber']",
            "input[type='tel']",
            "input[name*='phone']",
            "input[id*='phone']",
        ]:
            try:
                el = curr_target.locator(sel).first
                if await el.is_visible(timeout=1500) and phone:
                    await el.triple_click()
                    await el.fill(str(phone))
                    await target.wait_for_timeout(300)
                    break
            except Exception:
                continue

        logger.info("[ContactInfo] Done.")

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
    # PHASE 4 — AI-powered question answering pipeline
    # ═══════════════════════════════════════════════════════════════════════

    async def _answer_additional_questions(
        self,
        target,
        profile_data: dict,
        resume_text: str,
        resume_file_path: Optional[str] = None,
    ) -> None:
        """
        Complete AI-powered question-answering pipeline using single-pass LLM.
        1. Clean and tag the active modal HTML (mutating live DOM with data-qa-idx).
        2. Call Gemini Flash to identify and answer all fields in a single pass.
        3. Fill fields with React-compatible Playwright interactions.
        4. Verify that all required fields are filled, and attempt a retry pass if needed.
        """
        logger.info("[Questions] ══ AI question-answering pipeline start (Single-Pass) ══")

        await self._wait_for_page_settle(target)

        # ── Step 1: Clean & tag modal HTML ────────────────────────────────
        html_content = await self._clean_and_tag_modal_html(target)
        if not html_content:
            logger.warning("[Questions] Failed to extract modal HTML. Skipping QA.")
            return

        # ── Step 2: Get answers from Gemini Flash in one pass ─────────────
        answers = await self._get_single_pass_answers(html_content, profile_data, resume_text)
        if not answers:
            logger.warning("[Questions] No answers generated by LLM.")
            return

        # ── Step 3: Fill every field ──────────────────────────────────────
        filled_count = 0
        for ans in answers:
            ok = await self._fill_field_robust(target, ans)
            if ok:
                filled_count += 1
            await target.wait_for_timeout(100)

        logger.info(f"[Questions] Pass 1 complete — {filled_count}/{len(answers)} fields filled.")

        # ── Step 4: Verify required fields ───────────────────────────────
        await target.wait_for_timeout(700)
        try:
            empty_required = await target.evaluate(
                """() => {
                    function isVisible(el) {
                        if (!el) return false;
                        let curr = el;
                        while (curr) {
                            const style = window.getComputedStyle(curr);
                            if (style.display === 'none' || style.visibility === 'hidden') return false;
                            curr = curr.parentElement;
                        }
                        return true;
                    }
                    const modalSelectors = [".jobs-easy-apply-modal", ".artdeco-modal", "[role='dialog']", "form", "body"];
                    let modal = null;
                    for (const sel of modalSelectors) {
                        const elements = Array.from(document.querySelectorAll(sel));
                        const visibleEl = elements.find(isVisible);
                        if (visibleEl) { modal = visibleEl; break; }
                    }
                    if (!modal) return [];

                    const fields = Array.from(modal.querySelectorAll("input, textarea, select"));
                    const empty = [];
                    const seenRadioGroups = new Set();

                    fields.forEach(el => {
                        if (!isVisible(el)) return;
                        const isRequired =
                            el.hasAttribute('required') ||
                            el.getAttribute('aria-required') === 'true';
                        if (!isRequired) return;

                        const type = el.tagName === 'SELECT'
                            ? 'select'
                            : (el.type || 'text');

                        if (type === 'radio') {
                            const name = el.name;
                            if (name) {
                                if (seenRadioGroups.has(name)) return;
                                seenRadioGroups.add(name);
                                const checked = modal.querySelector(
                                    `input[type="radio"][name="${CSS.escape(name)}"]:checked`
                                );
                                if (!checked) {
                                    empty.push({
                                        qa_idx: el.getAttribute('data-qa-idx') || '',
                                        type: 'radio',
                                        name: name,
                                        label: el.id || name
                                    });
                                }
                            } else if (!el.checked) {
                                empty.push({
                                    qa_idx: el.getAttribute('data-qa-idx') || '',
                                    type: 'radio',
                                    name: '',
                                    label: el.id || ''
                                });
                            }
                        } else if (type === 'checkbox') {
                            if (!el.checked) {
                                empty.push({
                                    qa_idx: el.getAttribute('data-qa-idx') || '',
                                    type: 'checkbox',
                                    name: el.name || '',
                                    label: el.id || ''
                                });
                            }
                        } else if (type === 'select') {
                            if (!el.value.trim() || el.value.toLowerCase().includes('select')) {
                                empty.push({
                                    qa_idx: el.getAttribute('data-qa-idx') || '',
                                    type: 'select',
                                    name: el.name || '',
                                    label: el.id || ''
                                });
                            }
                        } else {
                            if (!el.value.trim()) {
                                empty.push({
                                    qa_idx: el.getAttribute('data-qa-idx') || '',
                                    type: type,
                                    name: el.name || '',
                                    label: el.id || el.placeholder || ''
                                });
                            }
                        }
                    });
                    return empty;
                }"""
            )
        except Exception as exc:
            logger.warning(
                f"[Questions] Context destroyed or navigation occurred during verification: {exc}."
            )
            return

        # ── Step 5: Retry if empty required fields remain ─────────────────
        if empty_required:
            logger.warning(
                f"[Questions] {len(empty_required)} required field(s) still empty after pass 1: "
                f"{[f.get('label') or f.get('name') for f in empty_required]} "
                f"— retrying with updated HTML state..."
            )
            html_content_retry = await self._clean_and_tag_modal_html(target)
            if html_content_retry:
                retry_answers = await self._get_single_pass_answers(
                    html_content_retry, profile_data, resume_text
                )
                retry_filled = 0
                for ans in retry_answers:
                    if any(f.get("qa_idx") == ans.get("qa_idx") for f in empty_required):
                        ok = await self._fill_field_robust(target, ans)
                        if ok:
                            retry_filled += 1
                        await target.wait_for_timeout(100)
                logger.info(f"[Questions] Retry pass complete — {retry_filled} field(s) filled.")
        else:
            logger.info("[Questions] ✓ All required fields verified filled.")

        logger.info("[Questions] ══ Done ══")

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

        context = None
        try:
            async with async_playwright() as pw:
                platform_name = "indeed" if is_indeed else "linkedin"
                user_data_dir = os.path.join(settings.USER_DATA_DIR, platform_name)
                os.makedirs(user_data_dir, exist_ok=True)

                # Pre-emptively remove stale Chromium SingletonLock file
                lock_file = os.path.join(user_data_dir, "SingletonLock")
                if os.path.exists(lock_file):
                    try:
                        logger.info("Pre-emptively removing stale browser SingletonLock file")
                        os.remove(lock_file)
                    except Exception as e:
                        logger.warning(f"Could not pre-emptively remove browser SingletonLock: {e}")

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
                        logger.warning(f"Browser locked, retry {attempt + 2}/3: {exc}")
                        # Cross-platform process killing using psutil
                        try:
                            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                                try:
                                    proc_name = (proc.info['name'] or '').lower()
                                    if 'chrome' in proc_name or 'chromium' in proc_name:
                                        exe_path = (proc.info['exe'] or '').lower()
                                        if 'ms-playwright' in exe_path:
                                            logger.info(f"Killing orphaned Playwright browser process: {proc.info['name']} (PID: {proc.info['pid']})")
                                            proc.kill()
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    pass
                        except Exception as kill_err:
                            logger.warning(f"Could not kill orphaned chrome processes: {kill_err}")
                        
                        # Remove stale Chromium lock file
                        if os.path.exists(lock_file):
                            try:
                                os.remove(lock_file)
                            except Exception:
                                pass
                        await asyncio.sleep(2)

                page = context.pages[0] if context.pages else await context.new_page()

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
                    platform_name = "Indeed" if is_indeed else "LinkedIn"
                    return {"status": "error", "message": f"{platform_name} session expired. Reconnect in Settings."}

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

                # ── Main step loop ────────────────────────────────────────────
                MAX_STEPS = 15
                for step_num in range(1, MAX_STEPS + 1):
                    # Resolve active target context (Page or Frame) and form locator
                    target, modal_locator = await handler.get_active_target(page)

                    await self._wait_for_page_settle(target)
                    step_type = await handler.detect_easy_apply_step(target)
                    logger.info(f"━━ Step {step_num}/{MAX_STEPS}: [{step_type.upper()}] ━━")

                    if step_type == "success":
                        job.status = "applied"
                        db.commit()
                        break

                    elif step_type == "contact_info":
                        await self._fill_contact_info(target, profile_data)

                    elif step_type == "resume_upload":
                        await self._handle_resume_upload(target, resume_file_path)

                    elif step_type == "questions":
                        await self._answer_additional_questions(
                            target,
                            profile_data,
                            resume_text,
                            resume_file_path,
                        )

                    elif step_type == "review":
                        submitted = await handler.handle_review_step(target, modal_locator, db, job)
                        if submitted:
                            break

                    elif step_type == "unknown":
                        logger.warning("Unknown step — attempting blind Next click.")

                    # Advance to next step only after current step is handled
                    clicked = await handler.click_next_or_review(target)
                    if not clicked:
                        logger.warning(
                            f"No navigation button found on step {step_num}. Stopping."
                        )
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
                if context:
                    await context.close()
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

    async def launch_login_browser(self, platform: str) -> None:
        """
        Open a persistent Chromium browser to the platform's login page.

        This is a lightweight flow — no automation, no form-filling. The user
        manually logs in; Playwright persists cookies/localStorage in the shared
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

        logger.info(f"[LoginBrowser] Launching browser for {platform} → {url}")
        context = None
        try:
            async with async_playwright() as pw:
                user_data_dir = os.path.join(settings.USER_DATA_DIR, platform.lower())
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