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

AGENT_SYSTEM_PROMPT = """\
You are an automated job-application assistant.

TOOL CONTRACT
Communicate ONLY through structured tool calls. No text, JSON, or thoughts.
Tools:
  fill_text(qa_idx, value)              — input text/numbers/URLs
  select_option(qa_idx, option_text)    — pick an <option>
  click_radio(qa_idx, label_text)       — select a radio button by label
  toggle_checkbox(qa_idx, checked)      — check/uncheck a checkbox
  click_navigation(action)             — "next" | "review" | "submit"
  upload_resume(reason)                — use if you see a Resume/CV file upload input
  declare_success(confirmation_text)   — signal application is successfully submitted
  report_blocked(reason, message)      — unrecoverable blocker (e.g., 0 fields found)

ANTI-HALLUCINATION & FALLBACK RULES
1. qa_idx MUST EXIST: You must visibly see data-qa-idx="…" in the HTML.
2. NO INVENTING: Values must come from Profile, pre-answered QA, or HTML text.
3. EXACT MATCH: option_text/label_text must match HTML text exactly.
4. SKIP FILLED: Ignore inputs with values or selected options (unless a blank placeholder).
5. FALLBACKS (If data is missing from profile):
   - Sensitive/EEO/Legal: Select "Decline to answer", "None", or skip if optional. NEVER guess.
   - Text inputs: "N/A"
   - URL inputs: "https://na.com"
   - Numbers: "0"
   - Dates: Current year / January
   - Other Selects/Radios: First non-blank option.

FIELD-SPECIFIC RULES
- First/Last Name: Split 'Full Name' logically if requested separately.
- Salary: Use expected_salary (or "Negotiable"/0).
- General Experience: Use total_years_experience as digits ("3").
- Skill Experience: Do NOT use total_years_experience for specific skills (e.g. "Experience with Java?"). Calculate years based on the Breakdown where the role matches the skill. If the skill is missing from Breakdown/Skills, enter "0".
- Visas/Sponsorship: Use work_authorization. NEVER guess sponsorship.
- Consents: ALWAYS check "Terms & Conditions", "Privacy", "Data Processing", or "Background Check" boxes.
- Marketing: Always UNCHECK "Follow company" or "Sign up for alerts".
- Cover Letter: If required, write a 2-sentence professional note using the Summary, or "N/A".
- Phone: Use profile.phone. Use select_option for country code if separate.

NAVIGATION
- Call click_navigation("next") when all visible fields are filled.
- Use "review" / "submit" ONLY if corresponding buttons exist.
- Call declare_success if page shows "Application sent", "Success", etc.
"""

# ─────────────────────────────────────────────────────────────────────────────
# USER TURN TEMPLATE  (rendered once per form step in run_screening_qa)
# ─────────────────────────────────────────────────────────────────────────────

AGENT_USER_TEMPLATE = """\
════════════════════════════════════════════
CANDIDATE PROFILE (NO INVENTING)
════════════════════════════════════════════
Name: {full_name} | Email: {email} | Phone: {phone_country_code} {phone} | Location: {location}
Experience: {total_years_experience} yrs (across {total_companies} companies) | Fields: {experience_fields}
Breakdown: {experience_breakdown}
Title: {previous_title} | Prev Co: {previous_company} ({previous_company_tenure})
Salary: {expected_salary} | Notice: {notice_period} | Auth: {work_authorization} | Relocate: {willing_to_relocate}
Skills: {skills}
Links: LinkedIn: {linkedin_url} | GitHub: {github_url} | Portfolio: {portfolio_url}
Education: {education}
Certifications: {certifications}
Summary: {summary}

════════════════════════════════════════════
DEMOGRAPHICS & PREFERENCES
════════════════════════════════════════════
Gender: {gender} | Disability: {disability_status} | Citizenship: {country_of_citizenship} | Needs Visa/Sponsorship: {requires_sponsorship}

════════════════════════════════════════════
ADDRESS
════════════════════════════════════════════
{address_line_1} {address_line_2}, {city}, {state_province} {postal_code}, {country}

════════════════════════════════════════════
PRE-ANSWERED QA
════════════════════════════════════════════
{qa_answers}

════════════════════════════════════════════
FORM HTML — Step {step_num}
════════════════════════════════════════════
{html}

TASK
1. Read elements with data-qa-idx.
2. Skip already filled elements.
3. Call tools to fill empty elements using ONLY profile/QA data or valid fallbacks.
4. Call click_navigation after handling all fields. No text output!\
"""

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
        "  • Use qa_idx values you can see in the Updated HTML below.\n"
        "  • Use values ONLY from the Candidate Profile already provided.\n"
        "  • Do NOT invent any value or qa_idx.\n"
        "  • After filling the missing fields, call click_navigation(action='next').\n\n"
        f"Updated HTML for step {step_num}:\n{new_html}"
    )

    return [
        *formatted_original,
        # Represent the first LLM turn (assistant tool calls)
        {"role": "assistant", "content": "", "tool_calls": first_attempt_tool_calls},
        # Correction instruction from the orchestrator
        {"role": "user", "content": retry_instruction},
    ]
