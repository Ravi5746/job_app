import logging
from app.services.automation.agent.state import ApplicationState, AppPhase

logger = logging.getLogger(__name__)


class HallucinationGuard:
    """
    Filters LLM tool calls that reference qa_idx values not present in the current HTML.
    Runs between LLM output and ToolRegistry execution.
    Navigation and terminal tools are always allowed through.
    """
    _NO_QA_IDX_TOOLS = {"click_navigation", "declare_success", "report_blocked", "upload_resume"}

    @classmethod
    def validate(cls, tool_calls: list[dict], valid_indices: set[str]) -> list[dict]:
        allowed = []
        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {})
            if "qa_idx" in args:
                # Normalize in place to clean arguments for downstream use
                args["qa_idx"] = cls._normalize_qa_idx(args["qa_idx"])

            qa_idx = args.get("qa_idx", "")
            if name in cls._NO_QA_IDX_TOOLS:
                allowed.append(tc)
            elif qa_idx in valid_indices:
                allowed.append(tc)
            else:
                logger.warning(f"[HallucinationGuard] REJECTED {name}(qa_idx={qa_idx!r})")
        return allowed

    @staticmethod
    def _normalize_qa_idx(qa_idx) -> str:
        if isinstance(qa_idx, dict):
            val = qa_idx.get("data-qa-idx") or qa_idx.get("qa_idx") or list(qa_idx.values())[0]
            return str(val).strip()
        return str(qa_idx).strip()


class SubmitGuard:
    """
    Blocks the 'submit' action unless state.phase == REVIEWING.
    Prevents premature submission of incomplete applications.
    """
    @classmethod
    def check(cls, action: str, state: ApplicationState) -> str:
        if action == "submit" and state.phase != AppPhase.REVIEWING:
            logger.warning(
                f"[SubmitGuard] Blocked premature submit — phase is {state.phase.name}. "
                f"Downgrading to 'next'."
            )
            return "next"
        return action
