"""
agent_prompts.py — LangGraph job application agent prompts.

Design principles:
  1. GROUNDED — every tool call must reference a qa_idx value that exists
     verbatim in the HTML given to the model. The HallucinationGuard in
     guards.py rejects any call whose qa_idx is absent, but we reinforce
     that rule at the prompt level so the model understands *why*.
  2. CLOSED-WORLD — the model may only use values that appear in the
     candidate profile or the form HTML. It must never invent values.
  3. TOOL-FIRST — the model ONLY communicates via structured tool calls.
     It must not output any prose, JSON blobs, or markdown.
  4. RETRY-AWARE — the retry message carries an explicit diff of what
     failed; the model must act on only those fields and nothing else.
"""

from langchain_core.prompts import ChatPromptTemplate

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT  (used for every LLM call in run_screening_qa & run_retry_fill)
# ─────────────────────────────────────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """You are an automated job-application assistant.

Reply ONLY with tool calls. No prose, JSON, markdown, or thoughts.

Tools:
- fill_text(qa_idx, value)
- select_option(qa_idx, option_text)
- click_radio(qa_idx, label_text)
- toggle_checkbox(qa_idx, checked)
- click_navigation(action)  # next | review | submit
- upload_resume(reason)
- declare_success(confirmation_text)
- report_blocked(reason, message)

Rules:
1) Use only qa_idx values that are visibly present in the current form schema.
2) Fill only empty fields. Skip any field that already has a value/selection, unless it is a blank placeholder like "Select an option".
3) Use only values from the profile, pre-answered QA, or visible schema text. Never invent values.
4) Exact match required for option_text and label_text.
5) If data is missing:
   - text: "N/A"
   - url: "https://na.com"
   - number: "0"
   - date: current year / January
   - sensitive/EEO/legal: "Decline to answer" or skip if optional
   - other select/radio: first non-blank option
6) General experience questions use total_years_experience.
7) Skill-specific questions must be calculated from the experience breakdown only think step by step to calulate years sum overlapping time only once, and return 0 if no evidence exists.
8) Consents like Terms, Privacy, Data Processing, Background Check: check them if present.
9) Marketing opt-ins like Follow company or Alerts: leave unchecked.
10) If all visible required empty fields are handled, click_navigation("next"). Use review/submit only if those buttons exist.
11) If the page shows a success message, call declare_success."""
# ─────────────────────────────────────────────────────────────────────────────
# USER TURN TEMPLATE  (rendered once per form step in run_screening_qa)
# ─────────────────────────────────────────────────────────────────────────────

AGENT_USER_TEMPLATE = """PROFILE
Name: {full_name}
Email: {email}
Phone: {phone_country_code} {phone}
Location: {location}
Experience: {total_years_experience} years across {total_companies} companies
Breakdown: {experience_breakdown}
Title: {previous_title}
Prev Co: {previous_company} ({previous_company_tenure})
Currently Working: {currently_working_status}
Salary: {expected_salary}
Notice: {notice_period}
Auth: {work_authorization}
Relocate: {willing_to_relocate}
Skills: {skills}
Links: LinkedIn {linkedin_url} | GitHub {github_url} | Portfolio {portfolio_url}
Education: {education}
Certifications: {certifications}
Summary: {summary}

PREFERENCES
Gender: {gender}
Disability: {disability_status}
Citizenship: {country_of_citizenship}
Needs sponsorship: {requires_sponsorship}

ADDRESS
{address_line_1} {address_line_2}, {city}, {state_province} {postal_code}, {country}

PRE-ANSWERED QA
{qa_answers}

FORM SCHEMA — Step {step_num}
{html}

Task: fill only the empty fields in the schema using the rules above, then click_navigation("next")."""
# ─────────────────────────────────────────────────────────────────────────────
# COMPILED CHAT PROMPT
# ─────────────────────────────────────────────────────────────────────────────

agent_prompt = ChatPromptTemplate.from_messages([
    ("system", AGENT_SYSTEM_PROMPT),
    ("human",  AGENT_USER_TEMPLATE),
])


# ─────────────────────────────────────────────────────────────────────────────
# RETRY MESSAGE BUILDER  (used in run_retry_fill when fields remain empty)
# ─────────────────────────────────────────────────────────────────────────────

def build_retry_messages(
    original_messages: list,
    first_attempt_tool_calls: list,
    unfilled_labels: list[str],
    new_html: str,
    step_num: int,
) -> list:
    """
    Appends the failed first-pass tool calls and a correction instruction so
    the LLM can issue a targeted second pass for only the remaining empty fields.

    Called by run_retry_fill in langgraph_helpers.py when
    dom.check_required_empty() still returns non-empty required fields after
    the first LLM pass (~10-15 % of steps).

    Parameters
    ----------
    original_messages      : the system + user messages from the first pass
    first_attempt_tool_calls: raw tool_calls payload from the first LLM response
    unfilled_labels        : human-readable labels of the still-empty fields
    new_html               : freshly scraped HTML after the first pass executed
    step_num               : current form step index (for logging context)
    """
    # Normalise original messages to LangChain-compatible dicts
    formatted_original = []
    for msg in original_messages:
        if isinstance(msg, tuple):
            formatted_original.append({"role": msg[0], "content": msg[1]})
        else:
            formatted_original.append(msg)

    retry_instruction = (
        f"CORRECTION PASS — Step {step_num}\n\n"
        f"The following required fields are STILL EMPTY after your previous tool calls:\n"
        f"  {unfilled_labels}\n\n"
        "Rules for this retry:\n"
        "  • Fill ONLY the fields listed above — do NOT re-fill anything already done.\n"
        "  • Use qa_idx values you can see in the Updated SCHEMA below.\n"
        "  • Use values ONLY from the Candidate Profile already provided.\n"
        "  • Do NOT invent any value or qa_idx.\n"
        "  • After filling the missing fields, call click_navigation(action='next').\n\n"
        f"Updated SCHEMA for step {step_num}:\n{new_html}"
    )

    tool_responses = []
    for tc in first_attempt_tool_calls:
        tool_responses.append({
            "role": "tool",
            "tool_call_id": tc.get("id"),
            "name": tc.get("function", {}).get("name"),
            "content": "Success/Attempted"
        })

    return [
        *formatted_original,
        # Represent the first LLM turn (assistant tool calls)
        {"role": "assistant", "content": "", "tool_calls": first_attempt_tool_calls},
        *tool_responses,
        # Correction instruction from the orchestrator
        {"role": "user", "content": retry_instruction},
    ]
