from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool


# ── Pydantic schemas (tool input definitions) ──────────────────────────────────

class FillTextInput(BaseModel):
    """Fill a text input or textarea with a value. Use for text, number, and multi-line fields."""
    qa_idx: str = Field(description="The data-qa-idx attribute value of the target element")
    value:  str = Field(description="The text to enter into the field")


class SelectOptionInput(BaseModel):
    """Select a value from a <select> dropdown. Use the EXACT visible option text from the HTML."""
    qa_idx:      str = Field(description="The data-qa-idx attribute value")
    option_text: str = Field(description="Exact visible text of the option. Copy it verbatim.")


class ClickRadioInput(BaseModel):
    """Select a radio button option when the user must choose one answer from labeled options."""
    qa_idx:     str = Field(description="The data-qa-idx attribute value")
    label_text: str = Field(description="Text of the label associated with the radio option")


class ToggleCheckboxInput(BaseModel):
    """Check or uncheck a checkbox input."""
    qa_idx:   str  = Field(description="The data-qa-idx attribute value")
    checked:  bool = Field(description="true to check the box, false to uncheck it")


class ClickNavigationInput(BaseModel):
    """
    Click the form navigation button to advance. Call ONLY after filling all visible fields.
    Use 'submit' only on the review step when the Submit button is visible.
    """
    action: Literal["next", "review", "submit"] = Field(
        description="Which navigation action to perform"
    )


class UploadResumeInput(BaseModel):
    """Trigger resume file upload when an upload input or button is present on the page."""
    reason: str = Field(
        default="Resume upload required",
        description="Brief reason why upload is needed (for logging)"
    )


class DeclareSuccessInput(BaseModel):
    """
    Call ONLY when the page visually confirms the application was submitted.
    Look for text like 'Application sent' or 'Successfully submitted'.
    """
    confirmation_text: str = Field(description="The exact confirmation text visible on screen")


class ReportBlockedInput(BaseModel):
    """Call when the form cannot proceed due to an unrecoverable external condition."""
    reason:  Literal["captcha", "login_required", "external_redirect", "unknown_form", "max_retries"]
    message: str = Field(description="Human-readable description of the block reason")


# ── StructuredTool wrappers (schema + name, no execution) ─────────────────────

def _noop(**kwargs) -> None:
    """Placeholder. All execution happens in ToolRegistry, never through LangChain."""
    pass


def _make_tool(name: str, schema: type[BaseModel]) -> StructuredTool:
    return StructuredTool.from_function(
        func=_noop,
        name=name,
        description=schema.__doc__ or "",
        args_schema=schema,
    )


AGENT_TOOLS: list[StructuredTool] = [
    _make_tool("fill_text",        FillTextInput),
    _make_tool("select_option",    SelectOptionInput),
    _make_tool("click_radio",      ClickRadioInput),
    _make_tool("toggle_checkbox",  ToggleCheckboxInput),
    _make_tool("click_navigation", ClickNavigationInput),
    _make_tool("upload_resume",    UploadResumeInput),
    _make_tool("declare_success",  DeclareSuccessInput),
    _make_tool("report_blocked",   ReportBlockedInput),
]
