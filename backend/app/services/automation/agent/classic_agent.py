import logging
import hashlib
import json
from typing import Optional
import time
from sqlalchemy.orm import Session
from app.core.config import settings


from app.services.automation.agent.state import ApplicationState, AppPhase, StepRecord
from app.services.automation.agent.dom_layer import DOMLayer
from app.services.automation.agent.tool_registry import ToolRegistry
from app.services.automation.agent.guards import HallucinationGuard, SubmitGuard
from app.services.automation.agent.deterministic_fill import fill_if_deterministic
from app.services.automation.agent.langgraph_helpers import (
    is_value_empty,
    is_contact_field,
    is_field_unfilled,
    extract_question_text,
    serialize_tool_answer
)
from app.services.automation.agent.qa_cache_service import qa_cache_service
from app.ai.agent_prompts import agent_prompt, build_retry_messages

logger = logging.getLogger(__name__)


class ClassicApplicationAgent:
    """
    Fallback loop-driven agent that drives one job application from modal-open to submitted.
    Used when the LangGraph agent fails to compile or initialize.
    """

    def __init__(
        self,
        llm,
        dom: DOMLayer,
        tools: ToolRegistry,
        profile: dict,
        resume_text: str,
        job_id: int,
        user_id: int,
        application_id: Optional[int] = None
    ):
        from app.ai.agent_tools import AGENT_TOOLS
        # Bind tools to the LLM so it uses structured tool calling and wrap with retries
        self._llm = llm.bind_tools(AGENT_TOOLS).with_retry(
            stop_after_attempt=5,
            wait_exponential_jitter=True
        )
        self._dom = dom
        self._tools = tools
        self._profile = profile
        self._resume_text = resume_text
        self.application_id = application_id
        self._state = ApplicationState(job_id=job_id, user_id=user_id)


    async def _try_deterministic_fill(self, target, tagged_fields: list[dict], db: Optional[Session] = None) -> list[dict]:
        """
        Pre-fills standard fields (phone, email, name, location, URLs) without calling the LLM.
        Also retrieves answers from Q&A Cache if available.
        Returns a list of remaining unfilled fields.
        """
        is_indeed = "indeed.com" in (getattr(target, "page", target).url.lower())
        if is_indeed:
            try:
                await self._tools._svc.indeed_handler.fill_phone_country_code(target, self._profile)
            except Exception as e:
                logger.warning(f"Failed to fill Indeed phone country code deterministically: {e}")

        unfilled = []
        async def fill_fn(tgt, field_ans):
            return await self._tools._svc._fill_field_robust(tgt, field_ans)

        # Get HTML context for question label extraction
        html = await self._dom.clean_and_tag(target, self._profile)

        for field in tagged_fields:
            if not is_field_unfilled(field, tagged_fields) and not is_contact_field(field):
                logger.debug(f"[Deterministic] Field '{field.get('name') or field.get('qa_idx')}' already has value. Skipping.")
                continue

            filled = await fill_if_deterministic(target, field, self._profile, fill_fn)
            if filled:
                logger.info(f"[Deterministic] Filled field {field.get('qa_idx')} using deterministic rules.")
                self._state.total_fields_filled += 1
                continue

            # Layer 2.5: Q&A Cache retrieval fallback
            if db:
                question_text = extract_question_text(field, html)
                if question_text and len(question_text) > 3:
                    cached_res = qa_cache_service.get_cached_answer(question_text, self._state.user_id, db)
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
                            logger.info(f"[QACache] Filled field {field.get('qa_idx')} with cached answer: {ans_val}")
                            self._state.total_fields_filled += 1
                            continue

            unfilled.append(field)
        return unfilled

    def _save_step_metrics(
        self,
        db: Optional[Session],
        step_num: int,
        phase: str,
        start_time: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        fields_attempted: int = 0,
        fields_filled: int = 0,
        error_message: Optional[str] = None
    ):
        """Save step metrics to database for observability."""
        if not db or not self.application_id:
            return
        try:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            
            # Determine model name
            model_name = ""
            llm = self._llm
            if llm:
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
                application_id=self.application_id,
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
                f"[Telemetry] Saved classic step {step_num} ({phase}): duration={duration_ms}ms, "
                f"tokens={input_tokens}in/{output_tokens}out, cost=${cost:.6f}"
            )
        except Exception as e:
            logger.error(f"[Telemetry] Failed to save classic step metrics: {e}")

    async def run_step(self, target, step_num: int, db: Optional[Session] = None) -> dict:
        """
        One form step: observe → deterministic fill → LLM fill → verify → navigate.
        Uses an explicit retry loop — no recursion.
        """
        t_start = time.perf_counter()
        record = self._state.begin_step(step_num)
        self._state.phase = AppPhase.OBSERVING

        # SUCCESS CHECK — scoped locator, not raw HTML
        if await self._dom.detect_success_element(target):
            self._state.phase = AppPhase.SUCCESS
            self._save_step_metrics(db, step_num, "success_detect", t_start)
            return {"status": "success", "message": "Success screen detected!"}

        for attempt in range(settings.MAX_FILL_RETRIES + 1):
            record.retry_count = attempt
            logger.info(f"[Agent] Loop step {step_num}, attempt {attempt}/{settings.MAX_FILL_RETRIES}")

            # Clean and tag modal HTML
            html = await self._dom.clean_and_tag(target, self._profile)
            if not html:
                logger.warning(f"[Agent] Failed to clean/tag modal HTML in step {step_num}")
                self._save_step_metrics(db, step_num, "failed_html", t_start, error_message="Failed to clean/tag modal HTML")
                return {"status": "error", "message": "Failed to clean and tag modal HTML."}

            record.html_length = len(html)
            tagged_indices = self._dom.extract_tagged_indices(html)
            tagged_fields = await self._dom.extract_tagged_fields(html)

            # Check success again after HTML cleaning
            if await self._dom.detect_success_element(target):
                self._state.phase = AppPhase.SUCCESS
                self._save_step_metrics(db, step_num, "success_detect_after_clean", t_start)
                return {"status": "success", "message": "Success screen detected!"}

            # DETERMINISTIC PRE-FILL — zero LLM calls for known fields
            unfilled_fields = await self._try_deterministic_fill(target, tagged_fields, db)
            logger.info(f"[Agent] Deterministic pre-fill complete. {len(unfilled_fields)} fields remaining.")

            # Hash comparison to detect stuck forms
            html_hash = hashlib.md5(html.encode("utf-8")).hexdigest()
            if attempt > 0 and html_hash == self._state.last_html_hash:
                logger.warning("[Agent] DOM did not change between retry attempts. Force advancing to break loop...")
                record.force_advanced = True
                self._state.phase = AppPhase.ADVANCING
                
                is_indeed = "indeed.com" in (getattr(target, "page", target).url.lower())
                handler = self._tools._svc.indeed_handler if is_indeed else self._tools._svc.linkedin_handler
                await handler.click_next_or_review(target)
                self._save_step_metrics(db, step_num, "stuck_form_force_advance", t_start)
                return {"status": "continue"}

            self._state.last_html_hash = html_hash

            # Prepare prompts
            qa_answers_str = ""
            for q, a in self._profile.get("questionnaire_answers", {}).items():
                qa_answers_str += f"Q: {q}\nA: {a}\n\n"

            work_auth = self._profile.get("work_authorization", "").strip() or "Will discuss during interview"
            
            city = self._profile.get("city", "").strip()
            state_prov = self._profile.get("state_province", "").strip()
            country = self._profile.get("country", "").strip()
            parts = [p for p in [city, state_prov, country] if p]
            location = ", ".join(parts) if parts else (self._profile.get("location", "").strip() or "United States")
            
            expected_salary = str(self._profile.get("expected_salary", "")).strip() or "Negotiable"

            # Extract previous company, title, and tenure
            previous_company = ""
            previous_title = ""
            previous_company_tenure = ""
            total_companies = 0
            experience_fields = []
            experience_breakdown = []
            
            work_exp = self._profile.get("work_experience", [])
            if work_exp and isinstance(work_exp, list):
                total_companies = len(work_exp)
                for job in work_exp:
                    if isinstance(job, dict):
                        t = job.get("title") or job.get("role") or "Role"
                        comp = job.get("company") or "Company"
                        start = str(job.get("start_date") or job.get("start_year") or "")
                        end = str(job.get("end_date") or job.get("end_year") or "Present")
                        tenure = f"{start}-{end}" if start else "Unknown"
                        
                        experience_breakdown.append(f"{comp} ({t}, {tenure})")
                        
                        if t and t != "Role" and t not in experience_fields:
                            experience_fields.append(t)
                            
                if len(work_exp) > 0 and isinstance(work_exp[0], dict):
                    first_job = work_exp[0]
                    previous_company = first_job.get("company", "")
                    previous_title = first_job.get("title") or first_job.get("role") or ""
                    start = first_job.get("start_date") or first_job.get("start_year")
                    end = first_job.get("end_date") or first_job.get("end_year")
                    if start and end:
                        previous_company_tenure = f"{start} to {end}"
                    elif start:
                        previous_company_tenure = f"Started {start}"
                    elif end:
                        previous_company_tenure = f"Ended {end}"

            input_vars = {
                "full_name": self._profile.get("full_name", ""),
                "email": self._profile.get("email", ""),
                "phone": self._profile.get("phone", ""),
                "phone_country_code": self._profile.get("phone_country_code", ""),
                "location": location,
                "total_years_experience": self._profile.get("total_years_experience", 0),
                "total_companies": total_companies,
                "experience_fields": ", ".join(experience_fields),
                "experience_breakdown": " | ".join(experience_breakdown),
                "previous_title": previous_title,
                "previous_company": previous_company,
                "previous_company_tenure": previous_company_tenure,
                "expected_salary": expected_salary,
                "notice_period": self._profile.get("notice_period", ""),
                "work_authorization": work_auth,
                "willing_to_relocate": "Yes" if self._profile.get("willing_to_relocate") else "No",
                "skills": ", ".join(self._profile.get("skills", [])),
                "linkedin_url": self._profile.get("linkedin_url", ""),
                "github_url": self._profile.get("github_url", ""),
                "portfolio_url": self._profile.get("portfolio_url", ""),
                "education": str(self._profile.get("education", [])),
                "certifications": str(self._profile.get("certifications", [])),
                "summary": self._profile.get("summary", ""),
                "qa_answers": qa_answers_str or "None available",
                "gender": self._profile.get("gender", ""),
                "disability_status": self._profile.get("disability_status", ""),
                "requires_sponsorship": "Yes" if self._profile.get("requires_sponsorship") else "No",
                "country_of_citizenship": self._profile.get("country_of_citizenship", ""),
                "preferred_work_models": ", ".join(self._profile.get("preferred_work_models", [])),
                "address_line_1": self._profile.get("address_line_1", ""),
                "address_line_2": self._profile.get("address_line_2", ""),
                "city": self._profile.get("city", ""),
                "state_province": self._profile.get("state_province", ""),
                "postal_code": self._profile.get("postal_code", ""),
                "country": self._profile.get("country", ""),
                "step_num": step_num,
                "html": html,
            }

            messages = agent_prompt.format_messages(**input_vars)

            # Context continuity on retries
            if attempt > 0:
                unfilled_labels = [f.get("aria-label") or f.get("name") or f.get("qa_idx") for f in unfilled_fields]
                prev_tool_calls_payload = []
                for tc in record.tool_calls_raw:
                    prev_tool_calls_payload.append({
                        "id": tc.get("id", f"call_{tc.get('name')}_{attempt}"),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc.get("args", {}))
                        }
                    })
                
                messages = build_retry_messages(
                    original_messages=messages,
                    first_attempt_tool_calls=prev_tool_calls_payload,
                    unfilled_labels=unfilled_labels,
                    new_html=html,
                    step_num=step_num
                )

            # Invoke LLM
            self._state.phase = AppPhase.THINKING
            record.llm_called = True
            self._state.total_llm_calls += 1

            input_tokens = 0
            output_tokens = 0
            t_llm_0 = time.perf_counter()
            try:
                response = await self._llm.ainvoke(messages)
                duration_llm = int((time.perf_counter() - t_llm_0) * 1000)
                if hasattr(response, "response_metadata") and response.response_metadata:
                    token_usage = response.response_metadata.get("token_usage", {})
                    if token_usage:
                        input_tokens = token_usage.get("prompt_tokens", 0) or token_usage.get("input_tokens", 0) or 0
                        output_tokens = token_usage.get("completion_tokens", 0) or token_usage.get("output_tokens", 0) or 0
                record.input_tokens += input_tokens
                record.output_tokens += output_tokens
                record.duration_ms += duration_llm
                
                tool_calls = getattr(response, "tool_calls", [])
                record.tool_calls_raw = tool_calls
                logger.info(f"[Agent] LLM returned {len(tool_calls)} tool calls.")
            except Exception as e:
                logger.error(f"[Agent] LLM invocation failed: {e}")
                self._save_step_metrics(db, step_num, "llm_failed", t_start, error_message=str(e))
                return {"status": "error", "message": f"LLM error: {e}"}

            # Filter hallucinated tool calls
            valid_calls = HallucinationGuard.validate(tool_calls, tagged_indices)
            record.tool_calls_valid = valid_calls
            record.hallucinations_blocked = len(tool_calls) - len(valid_calls)

            # Execute valid tools
            self._state.phase = AppPhase.FILLING
            filled_count = 0
            for tc in valid_calls:
                ok = await self._tools.execute(tc, target, state=self._state)
                if ok:
                    filled_count += 1
                    self._state.total_fields_filled += 1
                    
                    # Save LLM-generated answer to Q&A Cache if database is available
                    if db and "qa_idx" in tc.get("args", {}):
                        qa_idx = tc["args"]["qa_idx"]
                        corresp_field = next((f for f in unfilled_fields if f.get("qa_idx") == qa_idx), None)
                        if corresp_field:
                            q_text = extract_question_text(corresp_field, html)
                            a_text = serialize_tool_answer(tc)
                            if q_text and a_text:
                                qa_cache_service.save_to_cache(q_text, a_text, self._state.user_id, db)
                await target.wait_for_timeout(100)

            record.fields_filled += filled_count
            record.fields_attempted += len(valid_calls)

            # Check if success or blocked was declared by tools
            has_success = any(tc.get("name") == "declare_success" for tc in valid_calls)
            if has_success:
                self._state.phase = AppPhase.SUCCESS
                self._save_step_metrics(
                    db, step_num, "success_declared", t_start,
                    input_tokens=input_tokens, output_tokens=output_tokens,
                    fields_attempted=record.fields_attempted, fields_filled=record.fields_filled
                )
                return {"status": "success", "message": "LLM declared application success."}

            has_blocked = any(tc.get("name") == "report_blocked" for tc in valid_calls)
            if has_blocked:
                self._state.phase = AppPhase.BLOCKED
                self._save_step_metrics(
                    db, step_num, "blocked", t_start,
                    input_tokens=input_tokens, output_tokens=output_tokens,
                    fields_attempted=record.fields_attempted, fields_filled=record.fields_filled,
                    error_message=self._state.blocked_reason or "Form blocked."
                )
                return {"status": "blocked", "reason": self._state.blocked_reason or "Form blocked."}

            # Verify required fields
            self._state.phase = AppPhase.VERIFYING
            unfilled_required = await self._dom.check_required_empty(target)
            if not unfilled_required:
                logger.info("[Agent] All required fields are filled. Advancing step.")
                self._state.phase = AppPhase.ADVANCING
                
                # If LLM didn't call click_navigation explicitly, trigger it manually
                has_nav = any(tc.get("name") == "click_navigation" for tc in valid_calls)
                if not has_nav:
                    is_indeed = "indeed.com" in (getattr(target, "page", target).url.lower())
                    handler = self._tools._svc.indeed_handler if is_indeed else self._tools._svc.linkedin_handler
                    await handler.click_next_or_review(target)
                self._save_step_metrics(
                    db, step_num, "advance", t_start,
                    input_tokens=input_tokens, output_tokens=output_tokens,
                    fields_attempted=record.fields_attempted, fields_filled=record.fields_filled
                )
                return {"status": "continue"}

            logger.warning(f"[Agent] Required fields still empty: {unfilled_required}")

        # Max retries exceeded
        logger.error("[Agent] Max retries exceeded. Attempting blind navigation to proceed.")
        self._state.phase = AppPhase.ADVANCING
        is_indeed = "indeed.com" in (getattr(target, "page", target).url.lower())
        handler = self._tools._svc.indeed_handler if is_indeed else self._tools._svc.linkedin_handler
        await handler.click_next_or_review(target)
        self._save_step_metrics(
            db, step_num, "max_retries_exceeded", t_start,
            input_tokens=input_tokens, output_tokens=output_tokens,
            fields_attempted=record.fields_attempted, fields_filled=record.fields_filled,
            error_message="Max retries exceeded"
        )
        return {"status": "continue"}

