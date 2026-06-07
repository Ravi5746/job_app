import os
import sys
import re
import logging
import hashlib
from typing import Dict, Any, List, Optional
from langchain_core.runnables import RunnableConfig
import redis
import json
from playwright.async_api import Page, FileChooser, Frame
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.job import Job as JobModel
from app.models.resume import Resume as ResumeModel
from app.ai.hermes import hermes_agent
from app.ai.agent_llm import create_llm
from app.services.automation.agent.guards import HallucinationGuard, SubmitGuard
from app.services.automation.agent.deterministic_fill import fill_if_deterministic, _resolve_profile_value
from app.services.automation.agent.semantic_classifier import semantic_classifier
from app.services.automation.agent.qa_cache_service import qa_cache_service
from app.ai.agent_prompts import agent_prompt, build_retry_messages
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def extract_question_text(field: dict, html: str) -> str:
    """
    Extracts the most descriptive question text for a given field dict from minified HTML.
    Looks at aria-label, then associated label tag, then placeholder, then name.
    """
    aria_label = field.get("aria-label", "").strip()
    if aria_label and len(aria_label) > 3:
        return aria_label
        
    field_id = field.get("id", "").strip()
    if field_id and html:
        try:
            soup = BeautifulSoup(html, "html.parser")
            label_el = soup.find("label", attrs={"for": field_id})
            if label_el:
                lbl_text = label_el.get_text(strip=True)
                if lbl_text and len(lbl_text) > 3:
                    return lbl_text
        except Exception as e:
            logger.warning(f"Error parsing HTML with BeautifulSoup for field {field_id}: {e}")

    placeholder = field.get("placeholder", "").strip()
    if placeholder and len(placeholder) > 3:
        return placeholder

    name = field.get("name", "").strip()
    if name and len(name) > 3:
        return name
        
    return aria_label or placeholder or name or ""

def serialize_tool_answer(tc: dict) -> str:
    args = tc.get("args", {})
    name = tc.get("name", "")
    if name == "fill_text":
        return str(args.get("value", ""))
    elif name == "select_option":
        return str(args.get("option_text", ""))
    elif name == "click_radio":
        return str(args.get("label_text", ""))
    elif name == "toggle_checkbox":
        return "true" if args.get("checked") else "false"
    return ""

# Registry for active live targets during execution (isolated from state serialization)
active_targets: Dict[str, Dict[str, Any]] = {}

def get_target_context(config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config.get("configurable", {}).get("thread_id")
    if not thread_id or thread_id not in active_targets:
        raise RuntimeError(f"Thread ID {thread_id} not registered in active_targets registry.")
    return active_targets[thread_id]

async def run_browser_launch(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    ctx = get_target_context(config)
    svc = ctx["svc"]
    user_id = state["user_id"]
    job_id = state["job_id"]
    
    # Re-use pre-launched page if available
    if ctx.get("page"):
        logger.info("[LangGraph] Reusing pre-launched browser page context.")
        return {"status": "running"}
        
    db = ctx["db"]
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    is_indeed = "indeed.com" in job.url.lower()
    platform_name = "indeed" if is_indeed else "linkedin"
    
    # Launch persistent context
    browser_ctx = await svc._get_or_create_context(user_id, platform_name)
    page = await browser_ctx.new_page()
    await page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """
    )
    ctx["page"] = page
    ctx["target"] = page
    ctx["handler"] = svc.indeed_handler if is_indeed else svc.linkedin_handler
    
    return {"status": "running"}

async def run_navigate(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    ctx = get_target_context(config)
    page = ctx["page"]
    job_id = state["job_id"]
    db = ctx["db"]
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    
    # Re-use navigated page if already on the correct page
    if page.url != "about:blank" and (job.url in page.url or "jobs/view" in page.url or "apply.indeed.com" in page.url):
        logger.info("[LangGraph] Browser is already navigated to job page.")
        return {"status": "running"}
        
    target_url = job.url
    is_indeed = "indeed.com" in target_url.lower()
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
    
    # Handle search results click if on collection page
    if not is_indeed and ("jobs/search" in page.url or "jobs/collections" in page.url):
        for s_sel in [".job-card-container", ".jobs-search-results__list-item", ".jobs-search-results-list__item"]:
            try:
                item = page.locator(s_sel).first
                if await item.is_visible(timeout=3000):
                    await item.click()
                    await page.wait_for_timeout(3000)
                    break
            except Exception:
                continue
                
    await ctx["handler"].dismiss_popups(page)
    return {"status": "running"}

async def run_detect_step_type(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    ctx = get_target_context(config)
    page = ctx["page"]
    handler = ctx["handler"]
    dom = ctx["dom"]
    profile = state["profile"]
    
    # Locate active target (Page or Frame)
    target, modal_locator = await handler.get_active_target(page)
    ctx["target"] = target
    ctx["modal_locator"] = modal_locator
    await ctx["svc"]._wait_for_page_settle(target)
    
    # Detect step type
    step_type = await handler.detect_easy_apply_step(target)
    
    # Clean and tag modal HTML
    html = await dom.clean_and_tag(target, profile)
    tagged_fields = await dom.extract_tagged_fields(html) if html else []
    
    # Check success screen
    if step_type == "success" or await dom.detect_success_element(target):
        return {"step_type": "success", "accessible_fields": [], "status": "succeeded"}
        
    # Check session expiration
    if await handler.is_session_expired(page):
        raise RuntimeError("Session expired")
        
    return {
        "step_type": step_type,
        "accessible_fields": tagged_fields,
        "pending_fields": tagged_fields,
        "step_number": state["step_number"] + 1,
        "retry_count": 0
    }

async def run_contact_handler(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    ctx = get_target_context(config)
    target = ctx["target"]
    profile = state["profile"]
    accessible_fields = state["accessible_fields"]
    
    unfilled = []
    filled = dict(state["filled_fields"])
    async def fill_fn(tgt, field_ans):
        return await ctx["svc"]._fill_field_robust(tgt, field_ans)
        
    for field in accessible_fields:
        if field.get("value", "").strip():
            continue
            
        # Layer 1: Deterministic fill
        is_filled = await fill_if_deterministic(target, field, profile, fill_fn)
        if is_filled:
            filled[field["qa_idx"]] = True
            continue
            
        # Layer 2: Semantic classifier fill
        label = field.get("aria-label", "") or field.get("placeholder", "") or field.get("name", "") or field.get("id", "")
        if label:
            category, score = semantic_classifier.classify_field(label)
            if category:
                val = _resolve_profile_value(profile, category)
                if val:
                    ok = await fill_fn(target, {
                        "qa_idx": field["qa_idx"],
                        "type": field.get("type", "text"),
                        "answer": val,
                        "label": field.get("aria-label", ""),
                        "selector": "",
                    })
                    if ok:
                        filled[field["qa_idx"]] = True
                        continue
                        
        unfilled.append(field)
            
    return {"filled_fields": filled, "pending_fields": unfilled}

async def run_resume_upload(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    ctx = get_target_context(config)
    target = ctx["target"]
    resume_path = state["resume_path"]
    
    if resume_path:
        await ctx["svc"]._handle_resume_upload(target, resume_path)
        
    return {"status": "running"}

async def run_screening_qa(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    ctx = get_target_context(config)
    target = ctx["target"]
    profile = state["profile"]
    dom = ctx["dom"]
    tools = ctx["tools"]
    llm = ctx["llm"]
    db = ctx["db"]
    
    # Fetch initial HTML to extract descriptive question labels
    init_html = await dom.clean_and_tag(target, profile)
    
    # Layer 1 & 2: Pre-fill what we can
    filled = dict(state.get("filled_fields", {}))
    pending_fields = state.get("pending_fields", [])
    
    async def fill_fn(tgt, field_ans):
        return await ctx["svc"]._fill_field_robust(tgt, field_ans)
        
    remaining_fields = []
    for field in pending_fields:
        # Check if already filled
        if field.get("value", "").strip():
            filled[field["qa_idx"]] = True
            continue
            
        # Layer 1: Deterministic fill
        is_filled = await fill_if_deterministic(target, field, profile, fill_fn)
        if is_filled:
            filled[field["qa_idx"]] = True
            continue
            
        # Layer 2: Semantic classifier fill
        label = field.get("aria-label", "") or field.get("placeholder", "") or field.get("name", "") or field.get("id", "")
        if label:
            category, score = semantic_classifier.classify_field(label)
            if category:
                val = _resolve_profile_value(profile, category)
                if val:
                    ok = await fill_fn(target, {
                        "qa_idx": field["qa_idx"],
                        "type": field.get("type", "text"),
                        "answer": val,
                        "label": field.get("aria-label", ""),
                        "selector": "",
                    })
                    if ok:
                        filled[field["qa_idx"]] = True
                        continue
                        
        # Layer 2.5: Q&A Cache retrieval
        question_text = extract_question_text(field, init_html)
        if question_text and len(question_text) > 3:
            cached_res = qa_cache_service.get_cached_answer(question_text, db)
            if cached_res:
                ans_val, _ = cached_res
                ok = await fill_fn(target, {
                    "qa_idx": field["qa_idx"],
                    "type": field.get("type", "text"),
                    "answer": ans_val,
                    "label": "",
                    "selector": "",
                })
                if ok:
                    filled[field["qa_idx"]] = True
                    continue
                        
        remaining_fields.append(field)
        
    # If all fields are filled, we can skip the LLM call entirely!
    if not remaining_fields:
        logger.info("[ScreeningQA] All fields filled via Layer 1/2 pre-fill. Skipping LLM call.")
        return {"filled_fields": filled, "pending_fields": []}
        
    # Re-fetch HTML to reflect any filled fields if possible
    html = await dom.clean_and_tag(target, profile)
    if not html:
        return {"filled_fields": filled, "pending_fields": remaining_fields}
        
    tagged_indices = dom.extract_tagged_indices(html)
    qa_answers_str = "".join(f"Q: {q}\nA: {a}\n\n" for q, a in profile.get("questionnaire_answers", {}).items())
    
    input_vars = {
        "full_name": profile.get("full_name", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "phone_country_code": profile.get("phone_country_code", ""),
        "location": profile.get("location", ""),
        "total_years_experience": profile.get("total_years_experience", 0),
        "expected_salary": profile.get("expected_salary", "Negotiable"),
        "notice_period": profile.get("notice_period", ""),
        "work_authorization": profile.get("work_authorization", ""),
        "willing_to_relocate": "Yes" if profile.get("willing_to_relocate") else "No",
        "skills": ", ".join(profile.get("skills", [])),
        "linkedin_url": profile.get("linkedin_url", ""),
        "github_url": profile.get("github_url", ""),
        "portfolio_url": profile.get("portfolio_url", ""),
        "qa_answers": qa_answers_str or "None available",
        "step_num": state["step_number"],
        "html": html,
    }
    
    # Layer 3: LLM Fallback for truly novel fields
    messages = agent_prompt.format_messages(**input_vars)
    response = await llm.ainvoke(messages)
    tool_calls = getattr(response, "tool_calls", [])
    
    # Store raw tool calls for potential retries
    ctx["last_tool_calls"] = tool_calls
    ctx["last_html"] = html
    
    valid_calls = HallucinationGuard.validate(tool_calls, tagged_indices)
    
    for tc in valid_calls:
        ok = await tools.execute(tc, target, state=None)
        if ok and "qa_idx" in tc.get("args", {}):
            qa_idx = tc["args"]["qa_idx"]
            filled[qa_idx] = True
            
            # Save LLM-generated answer to Q&A Cache
            corresp_field = next((f for f in remaining_fields if f.get("qa_idx") == qa_idx), None)
            if corresp_field:
                q_text = extract_question_text(corresp_field, html)
                a_text = serialize_tool_answer(tc)
                if q_text and a_text:
                    qa_cache_service.save_to_cache(q_text, a_text, None, db)
                    
        await target.wait_for_timeout(100)
        
    return {"filled_fields": filled, "pending_fields": remaining_fields}


async def run_validate_fields(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    ctx = get_target_context(config)
    target = ctx["target"]
    dom = ctx["dom"]
    
    empty_required = await dom.check_required_empty(target)
    # Map back to accessible fields dictionary list
    pending = [f for f in state["accessible_fields"] if f.get("qa_idx") in empty_required or f.get("aria-label") in empty_required]
    
    return {"pending_fields": pending}


async def run_retry_fill(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    ctx = get_target_context(config)
    target = ctx["target"]
    dom = ctx["dom"]
    tools = ctx["tools"]
    llm = ctx["llm"]
    db = ctx["db"]
    
    html = await dom.clean_and_tag(target, state["profile"])
    tagged_indices = dom.extract_tagged_indices(html)
    unfilled_labels = [f.get("aria-label") or f.get("name") or f.get("qa_idx") for f in state["pending_fields"]]
    
    # Re-build messages using last raw tool calls
    prev_calls = ctx.get("last_tool_calls", [])
    prev_tool_calls_payload = []
    for idx, tc in enumerate(prev_calls):
        prev_tool_calls_payload.append({
            "id": tc.get("id", f"call_{tc.get('name')}_{idx}"),
            "type": "function",
            "function": {"name": tc["name"], "arguments": str(tc.get("args", {}))}
        })
        
    qa_answers_str = "".join(f"Q: {q}\nA: {a}\n\n" for q, a in state["profile"].get("questionnaire_answers", {}).items())
    input_vars = {
        "full_name": state["profile"].get("full_name", ""),
        "email": state["profile"].get("email", ""),
        "phone": state["profile"].get("phone", ""),
        "phone_country_code": state["profile"].get("phone_country_code", ""),
        "location": state["profile"].get("location", ""),
        "total_years_experience": state["profile"].get("total_years_experience", 0),
        "expected_salary": state["profile"].get("expected_salary", "Negotiable"),
        "notice_period": state["profile"].get("notice_period", ""),
        "work_authorization": state["profile"].get("work_authorization", ""),
        "willing_to_relocate": "Yes" if state["profile"].get("willing_to_relocate") else "No",
        "skills": ", ".join(state["profile"].get("skills", [])),
        "linkedin_url": state["profile"].get("linkedin_url", ""),
        "github_url": state["profile"].get("github_url", ""),
        "portfolio_url": state["profile"].get("portfolio_url", ""),
        "qa_answers": qa_answers_str or "None available",
        "step_num": state["step_number"],
        "html": ctx.get("last_html", ""),
    }
    
    orig_messages = agent_prompt.format_messages(**input_vars)
    messages = build_retry_messages(
        original_messages=orig_messages,
        first_attempt_tool_calls=prev_tool_calls_payload,
        unfilled_labels=unfilled_labels,
        new_html=html,
        step_num=state["step_number"]
    )
    
    response = await llm.ainvoke(messages)
    tool_calls = getattr(response, "tool_calls", [])
    valid_calls = HallucinationGuard.validate(tool_calls, tagged_indices)
    
    filled = dict(state["filled_fields"])
    for tc in valid_calls:
        ok = await tools.execute(tc, target, state=None)
        if ok and "qa_idx" in tc.get("args", {}):
            qa_idx = tc["args"]["qa_idx"]
            filled[qa_idx] = True
            
            # Save LLM-generated answer to Q&A Cache in retry step
            corresp_field = next((f for f in state["pending_fields"] if f.get("qa_idx") == qa_idx), None)
            if corresp_field:
                q_text = extract_question_text(corresp_field, html)
                a_text = serialize_tool_answer(tc)
                if q_text and a_text:
                    qa_cache_service.save_to_cache(q_text, a_text, None, db)
                    
        await target.wait_for_timeout(100)
        
    return {"filled_fields": filled, "retry_count": state["retry_count"] + 1}


async def run_advance_form(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    ctx = get_target_context(config)
    target = ctx["target"]
    handler = ctx["handler"]
    
    await handler.click_next_or_review(target)
    return {"status": "running"}

async def run_review(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    ctx = get_target_context(config)
    target = ctx["target"]
    modal_locator = ctx["modal_locator"]
    handler = ctx["handler"]
    db = ctx["db"]
    job_id = state["job_id"]
    
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    submitted = await handler.handle_review_step(target, modal_locator, db, job)
    
    if submitted:
        return {"status": "succeeded"}
    return {"status": "failed", "errors": ["Submit button not click-verified"]}

async def run_success(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    ctx = get_target_context(config)
    page = ctx["page"]
    job_id = state["job_id"]
    db = ctx["db"]
    
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    job.status = "applied"
    db.commit()
    
    os.makedirs(settings.SCREENSHOTS_DIR, exist_ok=True)
    screenshot_path = os.path.join(settings.SCREENSHOTS_DIR, f"job_{job_id}_applied.png")
    await page.screenshot(path=screenshot_path, full_page=True)
    await page.wait_for_timeout(2000)
    
    screenshot_paths = list(state["screenshot_paths"])
    screenshot_paths.append(screenshot_path)
    
    return {"status": "succeeded", "screenshot_paths": screenshot_paths}

async def run_human_review(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    # Custom notification/webhook or pause logic
    logger.error("State machine entered human_review node. Execution paused.")
    return {"status": "paused", "errors": ["Human review or missing required fields"]}
