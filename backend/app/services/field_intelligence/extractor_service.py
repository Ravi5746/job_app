import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Optional, List
from playwright.async_api import async_playwright

from app.db.session import SessionLocal
from app.models.extraction import ExtractionRun, ExtractedField, FieldStats
from app.models.user import User
from app.models.resume import Resume
from app.services.field_intelligence.ats_detector import detect_ats_dom
from app.services.field_intelligence.submit_guard import is_submit_button
from app.services.field_intelligence.field_classifier import classify
from app.services.field_intelligence.profile_filler import profile_fill_field
from app.core.config import settings
from app.services.automation_service import AutomationService

logger = logging.getLogger(__name__)

def compute_dom_hash(fields: List[dict], page_text_snippet: str = "") -> str:
    signals = {
        "field_count": len(fields),
        "fields": sorted([
            (
                f.get("label", ""),
                f.get("type", ""),
                f.get("name", ""),
                f.get("id", ""),
                f.get("required", False),
                len(f.get("options", [])) if f.get("options") else 0,
            )
            for f in fields
        ]),
        "text_fingerprint": page_text_snippet[:500],
    }
    raw = json.dumps(signals, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

class ExtractorService:
    def __init__(self):
        self.automation_service = AutomationService()
        self._dom_layer = self.automation_service._dom
        
        self.handlers = {
            "indeed": self.automation_service.indeed_handler,
            "linkedin": self.automation_service.linkedin_handler
        }

    async def execute(self, run_id: int, headless: Optional[bool] = None):
        if headless is None:
            headless = settings.HEADLESS
            
        db = SessionLocal()
        run = db.query(ExtractionRun).filter(ExtractionRun.id == run_id).first()
        if not run:
            db.close()
            return
            
        profile_data = {}
        resume = None
        if run.user_id:
            user = db.query(User).filter(User.id == run.user_id).first()
            if user:
                profile_data = user.to_profile_dict()
            resume = db.query(Resume).filter(Resume.user_id == run.user_id).first()

        run.status = "running"
        run.started_at = datetime.utcnow()
        db.commit()

        try:
            url_lower = (run.job_url or "").lower()
            is_indeed = "indeed.com" in url_lower
            is_linkedin = "linkedin.com" in url_lower
            platform = "indeed" if is_indeed else ("linkedin" if is_linkedin else None)
            handler = self.handlers.get(platform) if platform else None
            
            user_data_dir = None
            if platform and run.user_id:
                user_platform_dir = os.path.join(settings.USER_DATA_DIR, str(run.user_id), platform)
                marker_path = os.path.join(user_platform_dir, f"connected_{platform}.txt")
                if os.path.exists(marker_path):
                    user_data_dir = user_platform_dir
                    logger.info(f"Extractor: Using persistent browser context for user {run.user_id} on {platform}")

            async with async_playwright() as p:
                browser = None
                if user_data_dir:
                    # Pre-emptively remove stale Chromium SingletonLock file to avoid lock issues
                    lock_file = os.path.join(user_data_dir, "SingletonLock")
                    if os.path.exists(lock_file):
                        try:
                            logger.info("Extractor: Pre-emptively removing stale browser SingletonLock file")
                            os.remove(lock_file)
                        except Exception as e:
                            logger.warning(f"Extractor: Could not pre-emptively remove browser SingletonLock: {e}")
                            
                    context = await p.chromium.launch_persistent_context(
                        user_data_dir,
                        headless=headless,
                        channel="chrome",
                        locale="en-US",
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-infobars",
                        ],
                        viewport={"width": 1280, "height": 800},
                        ignore_default_args=["--enable-automation"],
                    )
                    page = context.pages[0] if context.pages else await context.new_page()
                else:
                    browser = await p.chromium.launch(headless=headless)
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        viewport={"width": 1280, "height": 800}
                    )
                    page = await context.new_page()
                
                # Navigate to the job listing page
                logger.info(f"Navigating to: {run.job_url}")
                await page.goto(run.job_url, timeout=60000)
                await page.wait_for_timeout(3000)

                # Detect ATS
                ats_type = await detect_ats_dom(page)
                run.ats_type = ats_type
                db.commit()

                # Attempt to find apply button and transition to form page
                if handler:
                    apply_button = await handler.find_apply_button(page)
                    if apply_button:
                        await apply_button.click()
                        await handler.wait_for_apply_interface(page)
                else:
                    # Fallback generic logic for unknown platforms
                    apply_button = None
                    apply_selectors = [
                        "button:has-text('Apply now')",
                        "button:has-text('Apply Now')",
                        "a:has-text('Apply')", 
                        "button:has-text('Apply')", 
                        "a:has-text('Submit')", 
                        "button:has-text('Submit')"
                    ]
                    for selector in apply_selectors:
                        try:
                            loc = page.locator(selector).first
                            if await loc.is_visible(timeout=2000):
                                apply_button = loc
                                break
                        except Exception:
                            continue
                            
                    if apply_button:
                        try:
                            async with page.expect_navigation(timeout=10000, wait_until="networkidle"):
                                await apply_button.click(timeout=5000)
                        except Exception:
                            try:
                                await apply_button.click(timeout=5000)
                            except Exception as e:
                                logger.warning(f"Could not click apply button: {e}")
                        await page.wait_for_timeout(3000)
                    else:
                        url_lower = page.url.lower()
                        if "apply" not in url_lower and "application" not in url_lower:
                            raise Exception("apply_button_not_found: No apply button visible and not on an application page.")
                
                step_number = 1
                total_fields = 0
                max_steps = 20
                stuck_retries = 0
                
                while step_number <= max_steps:
                    # Settle wait
                    await page.wait_for_timeout(2000)
                    
                    # Determine target (page or iframe)
                    if handler:
                        target, modal_locator = await handler.get_active_target(page)
                    else:
                        target = page
                    
                    # Extract raw fields via DOMLayer
                    raw_fields = await self._dom_layer.extract_structured_schema(target)
                    
                    # Save fields to db
                    step_field_count = 0
                    saved_fields = []
                    for f in raw_fields:
                        canonical = classify(
                            f.get("label", ""),
                            f.get("name", ""),
                            f.get("id", ""),
                            f.get("placeholder", ""),
                            f.get("aria_label", "")
                        )
                        
                        db_field = ExtractedField(
                            run_id=run.id,
                            step_number=step_number,
                            label=f.get("label"),
                            field_type=f.get("type", "text"),
                            required=f.get("required", False),
                            placeholder=f.get("placeholder"),
                            options=f.get("options"),
                            field_name=f.get("name"),
                            field_id=f.get("id"),
                            aria_label=f.get("aria_label"),
                            canonical_name=canonical
                        )
                        db.add(db_field)
                        step_field_count += 1
                        total_fields += 1
                        saved_fields.append(f)
                    
                    db.commit()
                    
                    # Get page text snippet
                    body_text = await target.inner_text("body")
                    current_hash = compute_dom_hash(saved_fields, body_text)
                    
                    # Profile fill required fields on this step to progress
                    for f in raw_fields:
                        if f.get("required") and f.get("id"):
                            locator = target.locator(f"#{f.get('id')}").first
                            if await locator.count() > 0:
                                canonical = classify(
                                    f.get("label", ""),
                                    f.get("name", ""),
                                    f.get("id", ""),
                                    f.get("placeholder", ""),
                                    f.get("aria_label", "")
                                )
                                await profile_fill_field(locator, f, canonical, profile_data, resume)
                                
                    # Press next using the handler
                    if handler:
                        nav_success = await handler.click_next_or_review(target)
                        if not nav_success:
                            logger.info("No explicit next/continue button found by handler, stopping execution.")
                            break
                    else:
                        # Fallback generic navigation
                        next_button = None
                        for text in ["next", "continue"]:
                            loc = target.locator(f"button:has-text('{text}')").first
                            try:
                                if await loc.is_visible(timeout=1000):
                                    next_button = loc
                                    break
                            except Exception:
                                pass
                        
                        if next_button:
                            try:
                                await next_button.click(timeout=5000)
                            except Exception as e:
                                logger.warning(f"Could not click next button: {e}")
                            await page.wait_for_timeout(3000)
                        else:
                            logger.info("No explicit next/continue button found, stopping execution.")
                            break
                        
                    new_body_text = await target.inner_text("body")
                    new_raw_fields = await self._dom_layer.extract_structured_schema(target)
                    new_hash = compute_dom_hash(new_raw_fields, new_body_text)
                    
                    if current_hash == new_hash:
                        stuck_retries += 1
                        if stuck_retries >= 3:
                            raise Exception("failed_stuck: form did not change structure after multiple navigation clicks.")
                    else:
                        stuck_retries = 0
                        step_number += 1
                
                run.status = "completed"
                run.total_steps = step_number
                run.total_fields = total_fields
                run.finished_at = datetime.utcnow()
                db.commit()

                # Update FieldStats counters
                fields_for_run = db.query(ExtractedField).filter(ExtractedField.run_id == run.id).all()
                for f in fields_for_run:
                    stats = db.query(FieldStats).filter(
                        FieldStats.canonical_name == f.canonical_name,
                        FieldStats.field_type == f.field_type,
                        FieldStats.required == f.required,
                        FieldStats.ats_type == run.ats_type,
                        FieldStats.company == run.company
                    ).first()
                    
                    if not stats:
                        stats = FieldStats(
                            canonical_name=f.canonical_name,
                            field_type=f.field_type,
                            required=f.required,
                            ats_type=run.ats_type,
                            company=run.company,
                            total_count=1
                        )
                        db.add(stats)
                    else:
                        stats.total_count += 1
                db.commit()
                
                if user_data_dir:
                    await context.close()
                else:
                    await browser.close()
                
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            run.status = "failed"
            run.error_message = str(e)
            db.commit()
        finally:
            db.close()
