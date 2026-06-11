import logging
from typing import TypedDict, List, Dict, Literal, Optional, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.core.config import settings, BASE_DIR

from app.services.automation.agent.langgraph_helpers import (
    active_targets,
    run_detect_step_type,
    run_contact_handler,
    run_resume_upload,
    run_screening_qa,
    run_validate_fields,
    run_retry_fill,
    run_advance_form,
    run_review,
    run_success,
    run_human_review
)

logger = logging.getLogger(__name__)

# Define TypedDict ApplicationState
class ApplicationState(TypedDict):
    job_id: int
    user_id: int
    profile: dict
    resume_path: Optional[str]
    step_number: int
    step_type: str  # contact_info, resume_upload, questions, review, success, human_review, unknown
    accessible_fields: List[Dict[str, Any]]
    filled_fields: Dict[str, bool]
    pending_fields: List[Dict[str, Any]]
    retry_count: int
    errors: List[str]
    screenshot_paths: List[str]
    status: Literal["running", "paused", "succeeded", "failed"]

# Router function after detect_step_type node
def route_after_detect(state: ApplicationState) -> str:
    step_type = state.get("step_type")
    status = state.get("status")
    if status == "succeeded" or step_type == "success":
        return "success"
    if status == "failed":
        return "human_review"
    if step_type == "review":
        return "review"
    if step_type == "resume_upload":
        return "resume_upload"
    if step_type == "contact_info":
        return "contact_handler"
    if step_type in ("questions", "unknown"):
        return "screening_qa"
    return "human_review"

# Router function after validate_fields node
def route_after_validation(state: ApplicationState) -> str:
    if not state.get("pending_fields"):
        return "advance_form"
    if state.get("retry_count", 0) >= settings.MAX_FILL_RETRIES:
        return "human_review"
    return "retry_fill"

# Router function after review node
def route_after_review(state: ApplicationState) -> str:
    if state.get("status") == "succeeded":
        return "success"
    # If review fails (e.g. required fields are still missing), route back to detect_step_type to re-evaluate the page
    return "detect_step_type"


class ApplicationAgent:
    """
    Drives one job application from modal-open to submitted using a compiled LangGraph workflow.
    Ensures state checkpoints are persisted in SQLite DB.
    """

    def __init__(
        self,
        llm,
        dom,
        tools,
        profile: dict,
        resume_text: str,
        job_id: int,
        user_id: int,
        application_id: Optional[int] = None
    ):
        from app.ai.agent_tools import AGENT_TOOLS
        # Bind tools to the LLM so it uses structured tool calling and wrap with retries
        self.llm = llm.bind_tools(AGENT_TOOLS)
        self.dom = dom
        self.tools = tools
        self.profile = profile
        self.resume_text = resume_text
        self.job_id = job_id
        self.user_id = user_id
        self.application_id = application_id

    async def run(self, page, db, handler, svc) -> dict:
        """
        Invokes the LangGraph state machine.
        """
        thread_id = f"{self.user_id}_{self.job_id}"
        logger.info(f"[LangGraph] Starting state machine execution for thread={thread_id}")

        # Register live objects into registry
        active_targets[thread_id] = {
            "page": page,
            "target": page,
            "svc": svc,
            "db": db,
            "tools": self.tools,
            "llm": self.llm,
            "dom": self.dom,
            "handler": handler,
            "application_id": self.application_id,
        }

        # Initialize base state
        initial_state = {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "profile": self.profile,
            "resume_path": getattr(svc, "_resume_path", None),
            "step_number": 0,
            "step_type": "unknown",
            "accessible_fields": [],
            "filled_fields": {},
            "pending_fields": [],
            "retry_count": 0,
            "errors": [],
            "screenshot_paths": [],
            "status": "running"
        }

        config = {"configurable": {"thread_id": thread_id}}

        try:
            # Construct state machine graph dynamically to avoid shared mutable state across threads
            builder = StateGraph(ApplicationState)

            # Add node definitions
            builder.add_node("detect_step_type", run_detect_step_type)
            builder.add_node("contact_handler", run_contact_handler)
            builder.add_node("resume_upload", run_resume_upload)
            builder.add_node("screening_qa", run_screening_qa)
            builder.add_node("validate_fields", run_validate_fields)
            builder.add_node("retry_fill", run_retry_fill)
            builder.add_node("advance_form", run_advance_form)
            builder.add_node("review", run_review)
            builder.add_node("success", run_success)
            builder.add_node("human_review", run_human_review)

            # Define transitions
            builder.add_edge(START, "detect_step_type")

            builder.add_conditional_edges(
                "detect_step_type",
                route_after_detect,
                {
                    "success": "success",
                    "review": "review",
                    "resume_upload": "resume_upload",
                    "contact_handler": "contact_handler",
                    "screening_qa": "screening_qa",
                    "human_review": "human_review"
                }
            )

            builder.add_edge("contact_handler", "validate_fields")
            builder.add_edge("resume_upload", "validate_fields")
            builder.add_edge("screening_qa", "validate_fields")

            builder.add_conditional_edges(
                "validate_fields",
                route_after_validation,
                {
                    "advance_form": "advance_form",
                    "human_review": "human_review",
                    "retry_fill": "retry_fill"
                }
            )

            builder.add_edge("retry_fill", "validate_fields")
            builder.add_edge("advance_form", "detect_step_type")

            builder.add_conditional_edges(
                "review",
                route_after_review,
                {
                    "success": "success",
                    "detect_step_type": "detect_step_type",
                    "human_review": "human_review"
                }
            )

            builder.add_edge("success", END)
            builder.add_edge("human_review", END)

            # Setup persistent SQLite checkpointer saver asynchronously using absolute path
            import os
            checkpoint_db_path = os.path.join(str(BASE_DIR), "checkpoints.db")
            async with AsyncSqliteSaver.from_conn_string(checkpoint_db_path) as checkpointer:
                graph = builder.compile(checkpointer=checkpointer)
                
                # Execute the state machine workflow
                final_state = await graph.ainvoke(initial_state, config=config)
                
                status = final_state.get("status", "failed")
                if status == "succeeded":
                    return {
                        "status": "success",
                        "message": "Application submitted successfully via LangGraph state machine.",
                        "screenshot": final_state.get("screenshot_paths", [""])[-1]
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Execution finished with status '{status}': {', '.join(final_state.get('errors', []))}"
                    }
        finally:
            # Clean up target registry
            active_targets.pop(thread_id, None)
