from langchain_core.prompts import ChatPromptTemplate

AGENT_SYSTEM_PROMPT = """You are filling a job application form on behalf of a candidate.
You receive: (1) minified form HTML with data-qa-idx attributes tagging every field, \
(2) candidate profile, and (3) pre-answered screening questions.

STRICT RULES:
- Call fill_text, select_option, click_radio, or toggle_checkbox for EVERY visible \
field that has a data-qa-idx attribute.
- Use the EXACT option text from <option> or label elements. Do not rephrase or translate.
- If a field already has a value= attribute set, SKIP it — it is already filled.
- For salary: always use the profile's expected_salary. If missing, use "Negotiable".
- For years of experience: derive from the profile's total_years_experience field.
- For work authorization questions: use profile.work_authorization verbatim.
- For notice period: use profile.notice_period verbatim.
- For "follow company" or "sign up for alerts" checkboxes: UNCHECK them (checked=false).
- After filling ALL fields, call click_navigation with action=next (or review/submit if visible).
- If the page shows "Application sent", "Successfully submitted", or similar: call declare_success.
- NEVER invent a qa_idx. Only use values you can see in the provided HTML.
- If a required field has no profile answer, use a reasonable professional default and log it.
- For questionnaire answers: if the question matches a pre-answered question below, use that answer EXACTLY.
"""

AGENT_USER_TEMPLATE = """\
=== CANDIDATE PROFILE ===
Name: {full_name}
Email: {email}
Phone Country Code: {phone_country_code}
Phone: {phone}
Location: {location}
Total Experience: {total_years_experience} years
Expected Salary: {expected_salary}
Notice Period: {notice_period}
Work Authorization: {work_authorization}
Willing to Relocate: {willing_to_relocate}
Skills: {skills}
LinkedIn: {linkedin_url}
GitHub: {github_url}
Portfolio: {portfolio_url}

=== PRE-ANSWERED SCREENING QUESTIONS ===
{qa_answers}

=== FORM HTML (step {step_num}) ===
{html}

Analyse every data-qa-idx element above. Fill each one using the appropriate tool, \
then call click_navigation to advance the form."""

agent_prompt = ChatPromptTemplate.from_messages([
    ("system", AGENT_SYSTEM_PROMPT),
    ("human",  AGENT_USER_TEMPLATE),
])


def build_retry_messages(
    original_messages: list,
    first_attempt_tool_calls: list,
    unfilled_labels: list[str],
    new_html: str,
    step_num: int,
) -> list:
    """
    Append the failed attempt and updated HTML for a second LLM pass.
    Used when required fields remain empty after the first pass (~10-15% of steps).
    """
    # LangChain messages standard formats require objects or dictionaries
    # Structured as role/content or message objects
    formatted_original = []
    for msg in original_messages:
        if isinstance(msg, tuple):
            formatted_original.append({"role": msg[0], "content": msg[1]})
        else:
            formatted_original.append(msg)
            
    return [
        *formatted_original,
        {"role": "assistant", "content": "", "tool_calls": first_attempt_tool_calls},
        {
            "role": "user",
            "content": (
                f"These required fields are still empty after your previous fills: "
                f"{unfilled_labels}. "
                f"Updated form HTML for step {step_num}:\n{new_html}\n"
                f"Fill only the remaining empty fields, then call click_navigation."
            ),
        },
    ]
