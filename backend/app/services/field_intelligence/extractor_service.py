import asyncio
import hashlib
import json
import logging
from datetime import datetime
from typing import Optional, List
from playwright.async_api import async_playwright

from app.db.session import SessionLocal
from app.models.extraction import ExtractionRun, ExtractedField, FieldStats
from app.services.field_intelligence.ats_detector import detect_ats_dom
from app.services.field_intelligence.submit_guard import is_submit_button
from app.services.field_intelligence.field_classifier import classify
from app.services.field_intelligence.fake_filler import fake_fill_field
from app.services.automation.agent.dom_layer import DOMLayer

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
        self._dom_layer = DOMLayer()

    async def execute(self, run_id: int):
        db = SessionLocal()
        run = db.query(ExtractionRun).filter(ExtractionRun.id == run_id).first()
        if not run:
            db.close()
            return
            
        run.status = "running"
        run.started_at = datetime.utcnow()
        db.commit()

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                # Create a throwaway page context
                context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
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
                apply_button = None
                for selector in ["a:has-text('Apply')", "button:has-text('Apply')", "a:has-text('Submit')", "button:has-text('Submit')"]:
                    loc = page.locator(selector).first
                    if await loc.count() > 0:
                        apply_button = loc
                        break
                
                if apply_button:
                    try:
                        async with page.expect_navigation(timeout=10000, wait_until="networkidle"):
                            await apply_button.click()
                    except Exception:
                        await apply_button.click()
                        await page.wait_for_timeout(3000)
                
                step_number = 1
                total_fields = 0
                max_steps = 20
                stuck_retries = 0
                
                while step_number <= max_steps:
                    # Settle wait
                    await page.wait_for_timeout(2000)
                    
                    # Extract raw fields via DOMLayer
                    raw_fields = await self._dom_layer.extract_structured_schema(page)
                    
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
                    body_text = await page.inner_text("body")
                    current_hash = compute_dom_hash(saved_fields, body_text)
                    
                    # Check next buttons
                    next_button = None
                    for text in ["next", "continue", "save & continue", "save and continue"]:
                        loc = page.locator(f"button:has-text('{text}')").first
                        if await loc.count() > 0:
                            next_button = loc
                            break
                    
                    if next_button:
                        btn_text = await next_button.inner_text()
                        if is_submit_button(btn_text):
                            logger.info("Next button is detected as a submit button! Stopping.")
                            break
                        
                        # Fake fill required fields on this step to progress
                        for f in raw_fields:
                            if f.get("required") and f.get("id"):
                                locator = page.locator(f"#{f.get('id')}").first
                                if await locator.count() > 0:
                                    await fake_fill_field(locator, f)
                        
                        # Press next
                        await next_button.click()
                        await page.wait_for_timeout(3000)
                        
                        new_body_text = await page.inner_text("body")
                        new_raw_fields = await self._dom_layer.extract_structured_schema(page)
                        new_hash = compute_dom_hash(new_raw_fields, new_body_text)
                        
                        if current_hash == new_hash:
                            stuck_retries += 1
                            if stuck_retries >= 3:
                                raise Exception("failed_stuck: form did not change structure after multiple navigation clicks.")
                        else:
                            stuck_retries = 0
                            step_number += 1
                    else:
                        logger.info("No explicit next/continue button found, stopping execution.")
                        break
                
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
                
                await browser.close()
                
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            run.status = "failed"
            run.error_message = str(e)
            db.commit()
        finally:
            db.close()
