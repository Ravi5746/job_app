# Refactoring Walkthrough — Prompt Centralization

I have successfully extracted all inline LLM prompts from the python source files and centralized them into a standalone module to improve maintainability and separate string templates from core execution logic.

## Changes Made

### 1. Created Centralized Prompts Module
*   **Path**: [app/ai/prompts.py](file:///d:/automation/Job%20Applied/backend/app/ai/prompts.py)
*   **Contents**: Contains modular, documented generator functions that return formatted prompt strings for all LLM tasks, including:
    *   `get_analyze_job_prompt()`
    *   `get_extract_job_details_prompt()`
    *   `get_calculate_match_score_prompt()`
    *   `get_optimize_resume_prompt()`
    *   `get_search_suggestions_prompt()`
    *   `get_generate_optimized_resume_for_role_prompt()`
    *   `get_generate_cover_letter_prompt()`
    *   `get_extract_profile_data_prompt()`
    *   `get_single_pass_answers_user_msg()` (updated with custom strict mapping prompt template)
    *   `SINGLE_PASS_FORM_SYSTEM_MSG` (constant string)

### 2. Custom Form Mapping Engine Prompt
*   Updated `get_single_pass_answers_user_msg` inside [prompts.py](file:///d:/automation/Job%20Applied/backend/app/ai/prompts.py#L249) to use the new strict, anti-hallucination **Resume-to-Job-Application Form Mapping Engine** prompt layout, which enforces strict guidelines for experience math, Work Authorization logic, option formatting, and output validation checks.

### 3. Refactored Hermes Agent
*   **Path**: [app/ai/hermes.py](file:///d:/automation/Job%20Applied/backend/app/ai/hermes.py)
*   **Refactoring**: Cleaned up the file by removing over 300 lines of inline prompt definitions, importing `app.ai.prompts` at the top, and calling the respective prompt generators before making API completions.

### 5. Fixed Contact Field Pre-fill (First Name / Last Name)
*   **Path**: [app/services/automation/agent/langgraph_helpers.py](file:///d:/automation/Job%20Applied/backend/app/services/automation/agent/langgraph_helpers.py#L134)
*   **Fix**: Modified the `is_contact_field` helper function to include `field.get("label", "")` in its evaluation list. Previously, it only checked `name`, `id`, `aria-label`, and `placeholder`.
*   **Impact**: When a form element uses an associated `<label>` tag for its description (such as "First name") but has a dynamic or auto-generated `id`/`name`, the agent now correctly identifies it as a contact field. This prevents the agent from skipping the field if it was pre-filled with incorrect default values.

---

## Verification Plan

### Automated Tests
*   Executed syntax check commands to compile `app/ai/prompts.py`:
    `.\venv\Scripts\python.exe -c "import app.ai.prompts; print('Imports compiled successfully!')"`
*   Executed syntax check commands to compile `app/services/automation/agent/langgraph_helpers.py`:
    `python -c "import app.services.automation.agent.langgraph_helpers; print('Code compiled successfully!')"`
*   Executed direct hermes extraction test script:
    `.\venv\Scripts\python.exe scratch\test_hermes_direct.py`
*   Verified that imports compile correctly, settings initialize properly, database connections succeed, and the refactored prompts route correctly to the Groq/OpenRouter client.
