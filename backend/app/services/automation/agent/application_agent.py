import logging
import hashlib
from app.core.config import settings
from app.services.automation.agent.state import ApplicationState, AppPhase, StepRecord
from app.services.automation.agent.dom_layer import DOMLayer
from app.services.automation.agent.tool_registry import ToolRegistry
from app.services.automation.agent.guards import HallucinationGuard, SubmitGuard
from app.services.automation.agent.deterministic_fill import fill_if_deterministic
from app.ai.agent_prompts import agent_prompt, build_retry_messages

logger = logging.getLogger(__name__)


class ApplicationAgent:
    """
    Drives one job application from modal-open to submitted.
    One instance per apply_to_job() call — never reuse across jobs.
    """

    def __init__(
        self,
        llm,
        dom: DOMLayer,
        tools: ToolRegistry,
        profile: dict,
        resume_text: str,
        job_id: int,
        user_id: int
    ):
        from app.ai.agent_tools import AGENT_TOOLS
        # Bind tools to the LLM so it uses structured tool calling
        self._llm = llm.bind_tools(AGENT_TOOLS)
        self._dom = dom
        self._tools = tools
        self._profile = profile
        self._resume_text = resume_text
        self._state = ApplicationState(job_id=job_id, user_id=user_id)

    async def _try_deterministic_fill(self, target, tagged_fields: list[dict]) -> list[dict]:
        """
        Pre-fills standard fields (phone, email, name, location, URLs) without calling the LLM.
        Returns a list of remaining unfilled fields.
        """
        unfilled = []
        # We define a helper fill function that delegates to self._tools._svc._fill_field_robust
        async def fill_fn(tgt, field_ans):
            return await self._tools._svc._fill_field_robust(tgt, field_ans)

        for field in tagged_fields:
            # Check if field already has a value
            if field.get("value", "").strip():
                logger.debug(f"[Deterministic] Field '{field.get('name') or field.get('qa_idx')}' already has value. Skipping.")
                continue

            filled = await fill_if_deterministic(target, field, self._profile, fill_fn)
            if filled:
                logger.info(f"[Deterministic] Filled field {field.get('qa_idx')} using deterministic rules.")
                self._state.total_fields_filled += 1
            else:
                unfilled.append(field)
        return unfilled

    async def run_step(self, target, step_num: int) -> dict:
        """
        One form step: observe → deterministic fill → LLM fill → verify → navigate.
        Uses an explicit retry loop — no recursion.
        """
        record = self._state.begin_step(step_num)
        self._state.phase = AppPhase.OBSERVING

        # SUCCESS CHECK — scoped locator, not raw HTML
        if await self._dom.detect_success_element(target):
            self._state.phase = AppPhase.SUCCESS
            return {"status": "success", "message": "Success screen detected!"}

        for attempt in range(settings.MAX_FILL_RETRIES + 1):
            record.retry_count = attempt
            logger.info(f"[Agent] Loop step {step_num}, attempt {attempt}/{settings.MAX_FILL_RETRIES}")

            # Clean and tag modal HTML
            html = await self._dom.clean_and_tag(target, self._profile)
            if not html:
                logger.warning(f"[Agent] Failed to clean/tag modal HTML in step {step_num}")
                return {"status": "error", "message": "Failed to clean and tag modal HTML."}

            record.html_length = len(html)
            tagged_indices = self._dom.extract_tagged_indices(html)
            tagged_fields = await self._dom.extract_tagged_fields(html)

            # Check success again after HTML cleaning
            if await self._dom.detect_success_element(target):
                self._state.phase = AppPhase.SUCCESS
                return {"status": "success", "message": "Success screen detected!"}

            # DETERMINISTIC PRE-FILL — zero LLM calls for known fields
            unfilled_fields = await self._try_deterministic_fill(target, tagged_fields)
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
                return {"status": "continue"}

            self._state.last_html_hash = html_hash

            # Prepare prompts
            qa_answers_str = ""
            for q, a in self._profile.get("questionnaire_answers", {}).items():
                qa_answers_str += f"Q: {q}\nA: {a}\n\n"

            input_vars = {
                "full_name": self._profile.get("full_name", ""),
                "email": self._profile.get("email", ""),
                "phone": self._profile.get("phone", ""),
                "phone_country_code": self._profile.get("phone_country_code", ""),
                "location": self._profile.get("location", ""),
                "total_years_experience": self._profile.get("total_years_experience", 0),
                "expected_salary": self._profile.get("expected_salary", "Negotiable"),
                "notice_period": self._profile.get("notice_period", ""),
                "work_authorization": self._profile.get("work_authorization", ""),
                "willing_to_relocate": "Yes" if self._profile.get("willing_to_relocate") else "No",
                "skills": ", ".join(self._profile.get("skills", [])),
                "linkedin_url": self._profile.get("linkedin_url", ""),
                "github_url": self._profile.get("github_url", ""),
                "portfolio_url": self._profile.get("portfolio_url", ""),
                "qa_answers": qa_answers_str or "None available",
                "step_num": step_num,
                "html": html,
            }

            messages = agent_prompt.format_messages(**input_vars)

            # Context continuity on retries
            if attempt > 0:
                unfilled_labels = [f.get("aria-label") or f.get("name") or f.get("qa_idx") for f in unfilled_fields]
                # Format previous tool calls for messages payload
                prev_tool_calls_payload = []
                for tc in record.tool_calls_raw:
                    prev_tool_calls_payload.append({
                        "id": tc.get("id", f"call_{tc.get('name')}_{attempt}"),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": str(tc.get("args", {}))
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

            try:
                response = await self._llm.ainvoke(messages)
                tool_calls = getattr(response, "tool_calls", [])
                record.tool_calls_raw = tool_calls
                logger.info(f"[Agent] LLM returned {len(tool_calls)} tool calls.")
            except Exception as e:
                logger.error(f"[Agent] LLM invocation failed: {e}")
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
                await target.wait_for_timeout(100)

            record.fields_filled += filled_count
            record.fields_attempted += len(valid_calls)

            # Check if success or blocked was declared by tools
            has_success = any(tc.get("name") == "declare_success" for tc in valid_calls)
            if has_success:
                self._state.phase = AppPhase.SUCCESS
                return {"status": "success", "message": "LLM declared application success."}

            has_blocked = any(tc.get("name") == "report_blocked" for tc in valid_calls)
            if has_blocked:
                self._state.phase = AppPhase.BLOCKED
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
                return {"status": "continue"}

            logger.warning(f"[Agent] Required fields still empty: {unfilled_required}")

        # Max retries exceeded
        logger.error("[Agent] Max retries exceeded. Attempting blind navigation to proceed.")
        self._state.phase = AppPhase.ADVANCING
        is_indeed = "indeed.com" in (getattr(target, "page", target).url.lower())
        handler = self._tools._svc.indeed_handler if is_indeed else self._tools._svc.linkedin_handler
        await handler.click_next_or_review(target)
        return {"status": "continue"}
