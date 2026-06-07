import logging
from app.services.automation.agent.dom_layer import DOMLayer
from app.services.automation.agent.state import ApplicationState
from app.services.automation.agent.guards import SubmitGuard

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Maps tool names to Playwright async execution functions.
    Tool definition (Pydantic schemas) is separate from tool execution (this class).
    """
    def __init__(self, dom_layer: DOMLayer, automation_service):
        self._dom = dom_layer
        self._svc = automation_service

    async def execute(self, tool_call: dict, target, state: ApplicationState = None) -> bool:
        name = tool_call["name"]
        args = tool_call.get("args", {})
        logger.info(f"[ToolRegistry] Executing tool {name} with args: {args}")

        try:
            if name == "fill_text":
                return await self._svc._fill_field_robust(target, {
                    "qa_idx": args["qa_idx"],
                    "type": "text",
                    "answer": args["value"],
                    "label": "",
                    "selector": ""
                })
            elif name == "select_option":
                return await self._svc._fill_field_robust(target, {
                    "qa_idx": args["qa_idx"],
                    "type": "select",
                    "answer": args["option_text"],
                    "label": "",
                    "selector": ""
                })
            elif name == "click_radio":
                return await self._svc._fill_field_robust(target, {
                    "qa_idx": args["qa_idx"],
                    "type": "radio",
                    "answer": args["label_text"],
                    "label": "",
                    "selector": ""
                })
            elif name == "toggle_checkbox":
                return await self._svc._fill_field_robust(target, {
                    "qa_idx": args["qa_idx"],
                    "type": "checkbox",
                    "answer": str(args["checked"]).lower(),
                    "label": "",
                    "selector": ""
                })
            elif name == "click_navigation":
                action = args.get("action", "next")
                if state:
                    action = SubmitGuard.check(action, state)
                
                # Check whether to use indeed or linkedin handler
                is_indeed = "indeed.com" in (getattr(target, "page", target).url.lower())
                handler = self._svc.indeed_handler if is_indeed else self._svc.linkedin_handler
                return await handler.click_next_or_review(target)
                
            elif name == "upload_resume":
                # Ensure resume path is passed or retrieved from service
                resume_path = getattr(self._svc, "_resume_path", None)
                if resume_path:
                    await self._svc._handle_resume_upload(target, resume_path)
                    return True
                else:
                    logger.warning("[ToolRegistry] No resume path set on service.")
                    return False
                    
            elif name == "declare_success":
                logger.info(f"[ToolRegistry] LLM declared success: {args.get('confirmation_text')}")
                return True
                
            elif name == "report_blocked":
                logger.warning(f"[ToolRegistry] LLM reported blocked: {args.get('reason')} - {args.get('message')}")
                if state:
                    state.blocked_reason = args.get("reason")
                return True

        except Exception as e:
            logger.error(f"[ToolRegistry] Error executing tool {name}: {e}")
            return False

        return False
