import os
import sys
import re
import logging
import time
import asyncio
from typing import Dict, Any, List, Optional
from langchain_core.runnables import RunnableConfig
import json
from playwright.async_api import Page, FileChooser, Frame
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.job import Job as JobModel
from app.models.resume import Resume as ResumeModel
from app.ai.hermes import hermes_agent
from app.ai.agent_llm import create_llm
from app.services.automation.agent.state import AppPhase
from app.services.automation.agent.guards import HallucinationGuard, SubmitGuard
from app.services.automation.agent.deterministic_fill import fill_if_deterministic, _resolve_profile_value
from app.services.automation.agent.qa_cache_service import qa_cache_service
from app.ai.agent_prompts import agent_prompt, build_retry_messages
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class LangGraphStateProxy:
    """A compatibility proxy wrapping the LangGraph dict state to match dataclass expected by ToolRegistry/SubmitGuard."""
    def __init__(self, state_dict: Dict[str, Any]):
        self._state_dict = state_dict

    @property
    def phase(self) -> AppPhase:
        step_type = self._state_dict.get("step_type")
        status = self._state_dict.get("status")
        if status == "succeeded":
            return AppPhase.SUCCESS
        if step_type == "review":
            return AppPhase.REVIEWING
        return AppPhase.OBSERVING

    @property
    def blocked_reason(self) -> Optional[str]:
        return self._state_dict.get("blocked_reason")

    @blocked_reason.setter
    def blocked_reason(self, val: Optional[str]):
        self._state_dict["blocked_reason"] = val
        self._state_dict["status"] = "paused"
        if "errors" not in self._state_dict:
            self._state_dict["errors"] = []
        self._state_dict["errors"].append(f"Blocked: {val}")

def record_step_metrics(
    config: RunnableConfig,
    step_num: int,
    phase: str,
    start_time: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
    fields_attempted: int = 0,
    fields_filled: int = 0,
    error_message: Optional[str] = None
):
    """Save an ApplicationStep record to the database for observability."""
    try:
        ctx = get_target_context(config)
        db = ctx.get("db")
        app_id = ctx.get("application_id")
        llm = ctx.get("llm")
        
        if not db or not app_id:
            logger.warning("[Telemetry] Missing DB or application_id in target context.")
            return

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        
        # Determine LLM model name to compute cost
        model_name = ""
        if llm:
            # Extract model name if possible from LangChain client
            if hasattr(llm, "model"):
                model_name = getattr(llm, "model", "")
            elif hasattr(llm, "model_name"):
                model_name = getattr(llm, "model_name", "")
            elif hasattr(llm, "primary") and hasattr(llm.primary, "model"):
                model_name = getattr(llm.primary, "model", "")
                
        from app.ai.agent_llm import calculate_llm_cost
        cost = calculate_llm_cost(model_name, input_tokens, output_tokens) if model_name else 0.0
        
        from app.models.application import ApplicationStep as ApplicationStepModel
        step_rec = ApplicationStepModel(
            application_id=app_id,
            step_num=step_num,
            phase=phase,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            fields_attempted=fields_attempted,
            fields_filled=fields_filled,
            error_message=error_message
        )
        db.add(step_rec)
        db.commit()
        logger.info(
            f"[Telemetry] Saved step {step_num} ({phase}): duration={duration_ms}ms, "
            f"tokens={input_tokens}in/{output_tokens}out, cost=${cost:.6f}, filled={fields_filled}/{fields_attempted}"
        )
    except Exception as e:
        logger.error(f"[Telemetry] Failed to save step metrics: {e}")

def is_value_empty(val: str) -> bool:

    if not val:
        return True
    val_clean = val.strip().lower()
    return not val_clean or val_clean in ("select an option", "select", "select_one", "--")

def is_field_unfilled(field: dict, all_fields: list[dict]) -> bool:
    ftype = field.get("type", "").lower()
    if ftype == "checkbox":
        return not field.get("checked", False)
    if ftype == "radio":
        name = field.get("name")
        if name:
            # Check if any radio in the same group is checked
            return not any(f.get("name") == name and f.get("checked", False) for f in all_fields)
        return not field.get("checked", False)
    val = field.get("value", "")
    return is_value_empty(val)

def is_contact_field(field: dict) -> bool:
    matchable_texts = [
        field.get("name", ""),
        field.get("id", ""),
        field.get("aria-label", ""),
        field.get("placeholder", ""),
        field.get("label", ""),
    ]
    combined = " ".join([t for t in matchable_texts if t]).lower()
    from app.services.automation.agent.deterministic_fill import DETERMINISTIC_FIELD_MAP
    for pattern, profile_key in DETERMINISTIC_FIELD_MAP.items():
        if re.search(pattern, combined, re.IGNORECASE):
            if profile_key in ("phone", "phone_country_code", "email", "first_name", "last_name", "full_name"):
                return True
    return False

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



async def run_detect_step_type(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    t0 = time.perf_counter()
    ctx = get_target_context(config)
    page = ctx["page"]
    handler = ctx["handler"]
    dom = ctx["dom"]
    profile = state["profile"]
    
    # Max form steps guard
    if state.get("step_number", 0) >= settings.MAX_FORM_STEPS:
        logger.warning(f"Max form steps reached ({state.get('step_number')}/{settings.MAX_FORM_STEPS}). Routing to human review.")
        record_step_metrics(config, state.get("step_number", 0), "detect_step_type_limit", t0, error_message="Max steps exceeded")
        return {
            "step_type": "human_review",
            "status": "paused",
            "errors": ["Max form steps limit reached"]
        }
        
    # Locate active target (Page or Frame)
    target, modal_locator = await handler.get_active_target(page)
    ctx["target"] = target
    ctx["modal_locator"] = modal_locator
    await ctx["svc"]._wait_for_page_settle(target)
    
    # Detect step type
    step_type = await handler.detect_easy_apply_step(target)
    
    # Extract structured fields
    structured_fields = await dom.extract_structured_schema(target, profile)
    
    # Check success screen
    if step_type == "success" or await dom.detect_success_element(target):
        record_step_metrics(config, state.get("step_number", 0) + 1, "detect_step_type", t0)
        return {"step_type": "success", "accessible_fields": [], "status": "succeeded"}
        
    # Check session expiration
    if await handler.is_session_expired(page):
        record_step_metrics(config, state.get("step_number", 0) + 1, "detect_step_type", t0, error_message="Session expired")
        raise RuntimeError("Session expired")
        
    record_step_metrics(config, state.get("step_number", 0) + 1, f"detect_step_type_{step_type}", t0)
    return {
        "step_type": step_type,
        "accessible_fields": structured_fields,
        "pending_fields": structured_fields,
        "step_number": state["step_number"] + 1,
        "retry_count": 0
    }


async def run_contact_handler(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    t0 = time.perf_counter()
    ctx = get_target_context(config)
    target = ctx["target"]
    profile = state["profile"]
    accessible_fields = state["accessible_fields"]
    
    # Fill country code if Indeed
    is_indeed = "indeed.com" in (getattr(target, "page", target).url.lower())
    if is_indeed:
        try:
            await ctx["svc"].indeed_handler.fill_phone_country_code(target, profile)
        except Exception as e:
            logger.warning(f"Failed to fill Indeed phone country code: {e}")

    unfilled = []
    filled = dict(state["filled_fields"])
    async def fill_fn(tgt, field_ans):
        return await ctx["svc"]._fill_field_robust(tgt, field_ans)
        
    for field in accessible_fields:
        val = field.get("value", "")
        # Do not skip if it's a contact info field (to allow updating pre-filled email/phone with correct profile values)
        if not is_value_empty(val) and not is_contact_field(field):
            continue
            
        # Layer 1: Deterministic fill
        is_filled = await fill_if_deterministic(target, field, profile, fill_fn)
        if is_filled:
            filled[field["qa_idx"]] = True
            continue
                        
        unfilled.append(field)
            
    fields_attempted = len(accessible_fields)
    fields_filled = len(filled) - len(state["filled_fields"])
    record_step_metrics(
        config, 
        state.get("step_number", 0), 
        "contact_handler", 
        t0, 
        fields_attempted=fields_attempted, 
        fields_filled=fields_filled
    )
    return {"filled_fields": filled, "pending_fields": unfilled}

async def run_resume_upload(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    t0 = time.perf_counter()
    ctx = get_target_context(config)
    target = ctx["target"]
    resume_path = state["resume_path"]
    
    if resume_path:
        await ctx["svc"]._handle_resume_upload(target, resume_path)
        
    record_step_metrics(
        config, 
        state.get("step_number", 0), 
        "resume_upload", 
        t0, 
        fields_attempted=1 if resume_path else 0, 
        fields_filled=1 if resume_path else 0
    )
    return {"status": "running"}


async def run_screening_qa(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    t0 = time.perf_counter()
    ctx = get_target_context(config)
    target = ctx["target"]
    profile = state["profile"]
    dom = ctx["dom"]
    tools = ctx["tools"]
    llm = ctx["llm"]
    db = ctx["db"]
    
    # Fetch initial structured schema to extract descriptive question labels
    init_fields = await dom.extract_structured_schema(target, profile)
    
    # Layer 1 & 2: Pre-fill what we can
    filled = dict(state.get("filled_fields", {}))
    pending_fields = state.get("pending_fields", [])
    
    async def fill_fn(tgt, field_ans):
        return await ctx["svc"]._fill_field_robust(tgt, field_ans)
        
    remaining_fields = []
    for field in pending_fields:
        if not is_field_unfilled(field, pending_fields) and not is_contact_field(field):
            filled[field["qa_idx"]] = True
            continue
            
        # Layer 1: Deterministic fill
        is_filled = await fill_if_deterministic(target, field, profile, fill_fn)
        if is_filled:
            filled[field["qa_idx"]] = True
            continue
                        
        # Layer 2.5: Q&A Cache retrieval
        question_text = field.get("label") or extract_question_text(field, "")
        if question_text and len(question_text) > 3:
            cached_res = qa_cache_service.get_cached_answer(question_text, state["user_id"], db)
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
        record_step_metrics(
            config,
            state.get("step_number", 0),
            "screening_qa_prefill",
            t0,
            fields_attempted=len(pending_fields),
            fields_filled=len(filled) - len(state.get("filled_fields", {}))
        )
        return {"filled_fields": filled, "pending_fields": []}
        
    # Re-extract structured fields and generate minified schema string
    current_fields = await dom.extract_structured_schema(target, profile)
    schema_str = dom.to_minified_schema_string(current_fields)
    if not schema_str:
        record_step_metrics(
            config,
            state.get("step_number", 0),
            "screening_qa_failed_html",
            t0,
            fields_attempted=len(pending_fields),
            fields_filled=len(filled) - len(state.get("filled_fields", {}))
        )
        return {"filled_fields": filled, "pending_fields": remaining_fields}
        
    tagged_indices = dom.extract_tagged_indices(schema_str)

    # ── Zero-field detection (Bug #3) ────────────────────────────────────────
    # If the scraper produced HTML with no interactive fields, calling the LLM
    # would result in it silently advancing the form without filling anything.
    # We detect this early and skip the LLM call so the validate_fields node
    # can mark these fields as pending and trigger a retry or human review.
    if not tagged_indices:
        logger.warning(
            "[ScreeningQA] SCRAPER ISSUE DETECTED: Schema contains zero indices. "
            f"Skipping LLM call. Step={state['step_number']}, schema_len={len(schema_str)}"
        )
        record_step_metrics(
            config,
            state.get("step_number", 0),
            "screening_qa_no_fields_in_html",
            t0,
            fields_attempted=len(pending_fields),
            fields_filled=0,
            error_message="Zero active fields found — likely scraper failure"
        )
        return {"filled_fields": filled, "pending_fields": remaining_fields}
    # ─────────────────────────────────────────────────────────────────────────

    qa_answers_str = "".join(f"Q: {q}\nA: {a}\n\n" for q, a in profile.get("questionnaire_answers", {}).items())

    # Normalise critical profile fields: replace empty strings with safe defaults
    # so the LLM never receives an empty work_authorization and hallucinate an answer
    work_auth = profile.get("work_authorization", "").strip() or "Will discuss during interview"
    
    city = profile.get("city", "").strip()
    state_prov = profile.get("state_province", "").strip()
    country = profile.get("country", "").strip()
    parts = [p for p in [city, state_prov, country] if p]
    location = ", ".join(parts) if parts else (profile.get("location", "").strip() or "United States")
    
    expected_salary = str(profile.get("expected_salary", "")).strip() or "Negotiable"

    # Extract previous company, title, and tenure
    previous_company = ""
    previous_title = ""
    previous_company_tenure = ""
    total_companies = 0
    experience_fields = []
    experience_breakdown = []
    
    work_exp = profile.get("work_experience", [])
    if work_exp and isinstance(work_exp, list):
        total_companies = len(work_exp)
        for job in work_exp:
            if isinstance(job, dict):
                t = job.get("title") or job.get("role") or job.get("job_title") or "Role"
                comp = job.get("company") or "Company"
                start = str(job.get("start") or job.get("start_date") or job.get("start_year") or "")
                end = str(job.get("end") or job.get("end_date") or job.get("end_year") or "Present")
                tenure = f"{start} to {end}" if start and end else (f"{start}-Present" if start else "Unknown")
                summary = job.get("summary") or job.get("description") or ""
                summary_clean = " ".join(summary.split())
                
                exp_str = f"{comp} ({t}, {tenure})"
                if summary_clean:
                    exp_str += f" - Summary: {summary_clean}"
                raw_skills = job.get("skills")
                skills_list = []
                if isinstance(raw_skills, list):
                    skills_list = [str(skill).strip() for skill in raw_skills if skill and str(skill).strip()]
                elif isinstance(raw_skills, str):
                    skills_list = [skill.strip() for skill in raw_skills.split(",") if skill.strip()]
                if skills_list:
                    exp_str += f" | Skills: {', '.join(skills_list)}"
                experience_breakdown.append(exp_str)
                
                if t and t != "Role" and t not in experience_fields:
                    experience_fields.append(t)
                    
        if len(work_exp) > 0 and isinstance(work_exp[0], dict):
            first_job = work_exp[0]
            previous_company = first_job.get("company", "")
            previous_title = first_job.get("title") or first_job.get("role") or ""
            start = first_job.get("start") or first_job.get("start_date") or first_job.get("start_year")
            end = first_job.get("end") or first_job.get("end_date") or first_job.get("end_year")
            if start and end:
                previous_company_tenure = f"{start} to {end}"
            elif start:
                previous_company_tenure = f"Started {start}"
            elif end:
                previous_company_tenure = f"Ended {end}"

    # Context-aware profile slicing
    needs_detailed_profile = False
    for field in remaining_fields:
        label = (field.get("label") or field.get("aria-label") or "").lower()
        if field.get("type") in ("textarea", "text") and not is_contact_field(field):
            if any(word in label for word in ["why", "describe", "explain", "project", "experience", "how", "tell", "responsibilit"]):
                needs_detailed_profile = True
                break

    skills_list = profile.get("skills", [])
    if not needs_detailed_profile and len(skills_list) > 10:
        skills_str = ", ".join(skills_list[:10]) + " (and others)"
    else:
        skills_str = ", ".join(skills_list)
        
    summary_str = profile.get("summary", "")
    if not needs_detailed_profile and len(summary_str) > 150:
        summary_str = summary_str[:150] + "..."
        
    experience_breakdown_str = " | ".join(experience_breakdown)

    input_vars = {
        "full_name": profile.get("full_name", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "phone_country_code": profile.get("phone_country_code", ""),
        "location": location,
        "total_years_experience": profile.get("total_years_experience", 0),
        "total_companies": total_companies,
        "experience_fields": ", ".join(experience_fields),
        "experience_breakdown": experience_breakdown_str,
        "previous_title": previous_title,
        "previous_company": previous_company,
        "previous_company_tenure": previous_company_tenure,
        "expected_salary": expected_salary,
        "notice_period": profile.get("notice_period", ""),
        "work_authorization": work_auth,
        "currently_working_status": (
            "Currently working" if profile.get("currently_working_status") is True
            else ("Not currently working" if profile.get("currently_working_status") is False else "Unknown")
        ),
        "willing_to_relocate": "Yes" if profile.get("willing_to_relocate") else "No",
        "skills": skills_str,
        "linkedin_url": profile.get("linkedin_url", ""),
        "github_url": profile.get("github_url", ""),
        "portfolio_url": profile.get("portfolio_url", ""),
        "education": str(profile.get("education", [])),
        "certifications": str(profile.get("certifications", [])),
        "summary": summary_str,
        "qa_answers": qa_answers_str or "None available",
        "gender": profile.get("gender", ""),
        "disability_status": profile.get("disability_status", ""),
        "requires_sponsorship": "Yes" if profile.get("requires_sponsorship") else "No",
        "country_of_citizenship": profile.get("country_of_citizenship", ""),
        "preferred_work_models": ", ".join(profile.get("preferred_work_models", [])),
        "address_line_1": profile.get("address_line_1", ""),
        "address_line_2": profile.get("address_line_2", ""),
        "city": profile.get("city", ""),
        "state_province": profile.get("state_province", ""),
        "postal_code": profile.get("postal_code", ""),
        "country": profile.get("country", ""),
        "step_num": state["step_number"],
        "html": schema_str,
    }
    
    # Layer 3: LLM Fallback for truly novel fields
    messages = agent_prompt.format_messages(**input_vars)
    
    input_tokens = 0
    output_tokens = 0
    max_retries = 3
    base_delay = 2.0
    response = None
    
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke(messages)
            if hasattr(response, "response_metadata") and response.response_metadata:
                token_usage = response.response_metadata.get("token_usage", {})
                if token_usage:
                    input_tokens = token_usage.get("prompt_tokens", 0) or token_usage.get("input_tokens", 0) or 0
                    output_tokens = token_usage.get("completion_tokens", 0) or token_usage.get("output_tokens", 0) or 0
            tool_calls = getattr(response, "tool_calls", [])
            break
        except Exception as llm_err:
            err_msg = str(llm_err).lower()
            is_transient = any(k in err_msg for k in ["429", "rate limit", "timeout", "503", "connection"])
            if is_transient and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[ScreeningQA] Transient LLM error: {llm_err}. Retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"[ScreeningQA] LLM invocation failed: {llm_err}")
                record_step_metrics(
                    config,
                    state.get("step_number", 0),
                    "screening_qa_failed_llm",
                    t0,
                    fields_attempted=len(pending_fields),
                    fields_filled=len(filled) - len(state.get("filled_fields", {})),
                    error_message=str(llm_err)
                )
                raise llm_err
        
    # Store raw tool calls for potential retries
    ctx["last_tool_calls"] = tool_calls
    ctx["last_html"] = schema_str
    
    valid_calls = HallucinationGuard.validate(tool_calls, tagged_indices)
    
    # Create compatibility state proxy
    state_proxy = LangGraphStateProxy(state)
    
    for tc in valid_calls:
        ok = await tools.execute(tc, target, state=state_proxy)
        if ok and "qa_idx" in tc.get("args", {}):
            qa_idx = tc["args"]["qa_idx"]
            filled[qa_idx] = True
            
            # Save LLM-generated answer to Q&A Cache
            corresp_field = next((f for f in remaining_fields if f.get("qa_idx") == qa_idx), None)
            if corresp_field:
                q_text = corresp_field.get("label") or extract_question_text(corresp_field, "")
                a_text = serialize_tool_answer(tc)
                if q_text and a_text:
                    qa_cache_service.save_to_cache(q_text, a_text, state["user_id"], db)
                    
        await target.wait_for_timeout(100)
        
    # Re-scan DOM to detect newly appeared (conditional) fields
    new_accessible_fields = list(state.get("accessible_fields", []))
    try:
        new_fields = await dom.extract_structured_schema(target, profile)
        new_schema_str = dom.to_minified_schema_string(new_fields)
        if new_schema_str:
            existing_indices = {f.get("qa_idx") for f in new_accessible_fields}
            for sf in new_fields:
                sf_idx = sf.get("qa_idx")
                if sf_idx and sf_idx not in existing_indices:
                    new_accessible_fields.append(sf)
                    # If it's not filled, add to remaining_fields
                    if sf_idx not in filled and not any(rf.get("qa_idx") == sf_idx for rf in remaining_fields):
                        remaining_fields.append(sf)
            logger.info(f"[ScreeningQA] DOM re-scanned. Total accessible: {len(new_accessible_fields)}, pending: {len(remaining_fields)}")
    except Exception as re_scan_err:
        logger.warning(f"[ScreeningQA] DOM re-scan failed: {re_scan_err}")

    fields_attempted = len(pending_fields)
    fields_filled = len(filled) - len(state.get("filled_fields", {}))
    
    record_step_metrics(
        config,
        state.get("step_number", 0),
        "screening_qa",
        t0,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        fields_attempted=fields_attempted,
        fields_filled=fields_filled
    )
    return {"filled_fields": filled, "pending_fields": remaining_fields, "accessible_fields": new_accessible_fields}



async def run_validate_fields(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    ctx = get_target_context(config)
    target = ctx["target"]
    dom = ctx["dom"]
    
    empty_required = await dom.check_required_empty(target)
    # Map back to accessible fields dictionary list using robust matching (qa_idx, aria-label, or name)
    pending = []
    for f in state.get("accessible_fields", []):
        qa_idx = f.get("qa_idx")
        aria_label = f.get("aria-label")
        name = f.get("name")
        if (
            (qa_idx and qa_idx in empty_required) or
            (aria_label and aria_label in empty_required) or
            (name and name in empty_required)
        ):
            pending.append(f)
            
    return {"pending_fields": pending}


async def run_retry_fill(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    t0 = time.perf_counter()
    ctx = get_target_context(config)
    target = ctx["target"]
    dom = ctx["dom"]
    tools = ctx["tools"]
    llm = ctx["llm"]
    db = ctx["db"]
    
    current_fields = await dom.extract_structured_schema(target, state["profile"])
    schema_str = dom.to_minified_schema_string(current_fields)
    tagged_indices = {f["qa_idx"] for f in current_fields if f.get("qa_idx")}
    unfilled_labels = [f.get("aria-label") or f.get("name") or f.get("qa_idx") for f in state["pending_fields"]]

    # ── Zero-field detection in retry pass ─────────────────────────────────
    if not tagged_indices:
        logger.warning(
            "[RetryFill] SCRAPER ISSUE DETECTED: Schema contains zero indices "
            "during retry pass. Skipping LLM call. "
            f"Step={state['step_number']}, schema_len={len(schema_str)}"
        )
        record_step_metrics(
            config,
            state.get("step_number", 0),
            "retry_fill_no_fields_in_html",
            t0,
            fields_attempted=len(state["pending_fields"]),
            fields_filled=0,
            error_message="Zero indices found in retry — likely scraper failure"
        )
        return {"retry_count": state["retry_count"] + 1}
    # ───────────────────────────────────────────────────────────────

    # Re-build messages using last raw tool calls
    prev_calls = ctx.get("last_tool_calls", [])
    prev_tool_calls_payload = []
    for idx, tc in enumerate(prev_calls):
        prev_tool_calls_payload.append({
            "id": tc.get("id", f"call_{tc.get('name')}_{idx}"),
            "type": "function",
            "function": {"name": tc["name"], "arguments": json.dumps(tc.get("args", {}))}
        })

    qa_answers_str = "".join(f"Q: {q}\nA: {a}\n\n" for q, a in state["profile"].get("questionnaire_answers", {}).items())
    work_auth = state["profile"].get("work_authorization", "").strip() or "Will discuss during interview"
    
    city = state["profile"].get("city", "").strip()
    state_prov = state["profile"].get("state_province", "").strip()
    country = state["profile"].get("country", "").strip()
    parts = [p for p in [city, state_prov, country] if p]
    location = ", ".join(parts) if parts else (state["profile"].get("location", "").strip() or "United States")
    
    expected_salary = str(state["profile"].get("expected_salary", "")).strip() or "Negotiable"

    previous_company = ""
    previous_title = ""
    previous_company_tenure = ""
    total_companies = 0
    experience_fields = []
    experience_breakdown = []
    
    work_exp = state["profile"].get("work_experience", [])
    if work_exp and isinstance(work_exp, list):
        total_companies = len(work_exp)
        for job in work_exp:
            if isinstance(job, dict):
                t = job.get("title") or job.get("role") or job.get("job_title") or "Role"
                comp = job.get("company") or "Company"
                start = str(job.get("start") or job.get("start_date") or job.get("start_year") or "")
                end = str(job.get("end") or job.get("end_date") or job.get("end_year") or "Present")
                tenure = f"{start} to {end}" if start and end else (f"{start}-Present" if start else "Unknown")
                summary = job.get("summary") or job.get("description") or ""
                summary_clean = " ".join(summary.split())
                
                exp_str = f"{comp} ({t}, {tenure})"
                if summary_clean:
                    exp_str += f" - Summary: {summary_clean}"
                raw_skills = job.get("skills")
                skills_list = []
                if isinstance(raw_skills, list):
                    skills_list = [str(skill).strip() for skill in raw_skills if skill and str(skill).strip()]
                elif isinstance(raw_skills, str):
                    skills_list = [skill.strip() for skill in raw_skills.split(",") if skill.strip()]
                if skills_list:
                    exp_str += f" | Skills: {', '.join(skills_list)}"
                experience_breakdown.append(exp_str)
                
                if t and t != "Role" and t not in experience_fields:
                    experience_fields.append(t)
                    
        if len(work_exp) > 0 and isinstance(work_exp[0], dict):
            first_job = work_exp[0]
            previous_company = first_job.get("company", "")
            previous_title = first_job.get("title") or first_job.get("role") or ""
            start = first_job.get("start") or first_job.get("start_date") or first_job.get("start_year")
            end = first_job.get("end") or first_job.get("end_date") or first_job.get("end_year")
            if start and end:
                previous_company_tenure = f"{start} to {end}"
            elif start:
                previous_company_tenure = f"Started {start}"
            elif end:
                previous_company_tenure = f"Ended {end}"

    # Context-aware profile slicing in retry
    needs_detailed_profile = False
    for field in state["pending_fields"]:
        label = (field.get("label") or field.get("aria-label") or "").lower()
        if field.get("type") in ("textarea", "text") and not is_contact_field(field):
            if any(word in label for word in ["why", "describe", "explain", "project", "experience", "how", "tell", "responsibilit"]):
                needs_detailed_profile = True
                break

    skills_list = state["profile"].get("skills", [])
    if not needs_detailed_profile and len(skills_list) > 10:
        skills_str = ", ".join(skills_list[:10]) + " (and others)"
    else:
        skills_str = ", ".join(skills_list)
        
    summary_str = state["profile"].get("summary", "")
    if not needs_detailed_profile and len(summary_str) > 150:
        summary_str = summary_str[:150] + "..."
        
    experience_breakdown_str = " | ".join(experience_breakdown)

    input_vars = {
        "full_name": state["profile"].get("full_name", ""),
        "email": state["profile"].get("email", ""),
        "phone": state["profile"].get("phone", ""),
        "phone_country_code": state["profile"].get("phone_country_code", ""),
        "location": location,
        "total_years_experience": state["profile"].get("total_years_experience", 0),
        "total_companies": total_companies,
        "experience_fields": ", ".join(experience_fields),
        "experience_breakdown": experience_breakdown_str,
        "previous_title": previous_title,
        "previous_company": previous_company,
        "previous_company_tenure": previous_company_tenure,
        "expected_salary": expected_salary,
        "notice_period": state["profile"].get("notice_period", ""),
        "work_authorization": work_auth,
        "currently_working_status": (
            "Currently working" if state["profile"].get("currently_working_status") is True
            else ("Not currently working" if state["profile"].get("currently_working_status") is False else "Unknown")
        ),
        "willing_to_relocate": "Yes" if state["profile"].get("willing_to_relocate") else "No",
        "skills": skills_str,
        "linkedin_url": state["profile"].get("linkedin_url", ""),
        "github_url": state["profile"].get("github_url", ""),
        "portfolio_url": state["profile"].get("portfolio_url", ""),
        "education": str(state["profile"].get("education", [])),
        "certifications": str(state["profile"].get("certifications", [])),
        "summary": summary_str,
        "qa_answers": qa_answers_str or "None available",
        "gender": state["profile"].get("gender", ""),
        "disability_status": state["profile"].get("disability_status", ""),
        "requires_sponsorship": "Yes" if state["profile"].get("requires_sponsorship") else "No",
        "country_of_citizenship": state["profile"].get("country_of_citizenship", ""),
        "preferred_work_models": ", ".join(state["profile"].get("preferred_work_models", [])),
        "address_line_1": state["profile"].get("address_line_1", ""),
        "address_line_2": state["profile"].get("address_line_2", ""),
        "city": state["profile"].get("city", ""),
        "state_province": state["profile"].get("state_province", ""),
        "postal_code": state["profile"].get("postal_code", ""),
        "country": state["profile"].get("country", ""),
        "step_num": state["step_number"],
        "html": ctx.get("last_html", ""),
    }
    
    orig_messages = agent_prompt.format_messages(**input_vars)
    messages = build_retry_messages(
        original_messages=orig_messages,
        first_attempt_tool_calls=prev_tool_calls_payload,
        unfilled_labels=unfilled_labels,
        new_html=schema_str,
        step_num=state["step_number"]
    )
    
    input_tokens = 0
    output_tokens = 0
    max_retries = 3
    base_delay = 2.0
    response = None
    
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke(messages)
            if hasattr(response, "response_metadata") and response.response_metadata:
                token_usage = response.response_metadata.get("token_usage", {})
                if token_usage:
                    input_tokens = token_usage.get("prompt_tokens", 0) or token_usage.get("input_tokens", 0) or 0
                    output_tokens = token_usage.get("completion_tokens", 0) or token_usage.get("output_tokens", 0) or 0
            tool_calls = getattr(response, "tool_calls", [])
            break
        except Exception as llm_err:
            err_msg = str(llm_err).lower()
            is_transient = any(k in err_msg for k in ["429", "rate limit", "timeout", "503", "connection"])
            if is_transient and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[RetryFill] Transient LLM error: {llm_err}. Retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"[RetryFill] LLM invocation failed: {llm_err}")
                record_step_metrics(
                    config,
                    state.get("step_number", 0),
                    "retry_fill_failed",
                    t0,
                    fields_attempted=len(state["pending_fields"]),
                    fields_filled=0,
                    error_message=str(llm_err)
                )
                raise llm_err
        
    valid_calls = HallucinationGuard.validate(tool_calls, tagged_indices)
    
    filled = dict(state["filled_fields"])
    state_proxy = LangGraphStateProxy(state)
    for tc in valid_calls:
        ok = await tools.execute(tc, target, state=state_proxy)
        if ok and "qa_idx" in tc.get("args", {}):
            qa_idx = tc["args"]["qa_idx"]
            filled[qa_idx] = True
            
            # Save LLM-generated answer to Q&A Cache in retry step
            corresp_field = next((f for f in state["pending_fields"] if f.get("qa_idx") == qa_idx), None)
            if corresp_field:
                q_text = corresp_field.get("label") or extract_question_text(corresp_field, "")
                a_text = serialize_tool_answer(tc)
                if q_text and a_text:
                    qa_cache_service.save_to_cache(q_text, a_text, state["user_id"], db)
                    
        await target.wait_for_timeout(100)
        
    # Re-scan DOM to detect newly appeared (conditional) fields in retry fill
    new_accessible_fields = list(state.get("accessible_fields", []))
    try:
        new_fields = await dom.extract_structured_schema(target, state["profile"])
        new_schema_str = dom.to_minified_schema_string(new_fields)
        if new_schema_str:
            existing_indices = {f.get("qa_idx") for f in new_accessible_fields}
            for sf in new_fields:
                sf_idx = sf.get("qa_idx")
                if sf_idx and sf_idx not in existing_indices:
                    new_accessible_fields.append(sf)
            logger.info(f"[RetryFill] DOM re-scanned. Total accessible: {len(new_accessible_fields)}")
    except Exception as re_scan_err:
        logger.warning(f"[RetryFill] DOM re-scan failed: {re_scan_err}")

    fields_attempted = len(state["pending_fields"])
    fields_filled = len(filled) - len(state["filled_fields"])
    record_step_metrics(
        config,
        state.get("step_number", 0),
        "retry_fill",
        t0,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        fields_attempted=fields_attempted,
        fields_filled=fields_filled
    )
    return {"filled_fields": filled, "retry_count": state["retry_count"] + 1, "accessible_fields": new_accessible_fields}

async def run_advance_form(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    t0 = time.perf_counter()
    ctx = get_target_context(config)
    target = ctx["target"]
    handler = ctx["handler"]
    
    clicked = await handler.click_next_or_review(target)
    record_step_metrics(config, state.get("step_number", 0), "advance_form", t0)
    
    if not clicked:
        logger.error("[AdvanceForm] Failed to find or click any Next/Review button.")
        return {"status": "failed", "errors": ["Failed to find Next or Review button. Form may be stuck."]}
        
    return {"status": "running"}

async def run_review(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    t0 = time.perf_counter()
    ctx = get_target_context(config)
    target = ctx["target"]
    modal_locator = ctx["modal_locator"]
    handler = ctx["handler"]
    db = ctx["db"]
    job_id = state["job_id"]
    
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    submitted = await handler.handle_review_step(target, modal_locator, db, job)
    
    if submitted:
        record_step_metrics(config, state.get("step_number", 0), "review_success", t0)
        return {"status": "succeeded"}
        
    record_step_metrics(config, state.get("step_number", 0), "review_failed", t0, error_message="Submit button not click-verified")
    return {"status": "failed", "errors": ["Submit button not click-verified"]}

async def run_success(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    t0 = time.perf_counter()
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
    
    record_step_metrics(config, state.get("step_number", 0), "success", t0)
    return {"status": "succeeded", "screenshot_paths": screenshot_paths}

async def run_human_review(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
    t0 = time.perf_counter()
    logger.error("State machine entered human_review node. Execution paused.")
    record_step_metrics(config, state.get("step_number", 0), "human_review", t0, error_message="Execution paused for human review")
    return {"status": "paused", "errors": ["Human review or missing required fields"]}

