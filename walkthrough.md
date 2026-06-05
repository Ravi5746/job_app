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

### 4. Refactored Automation Service
*   **Path**: [app/services/automation_service.py](file:///d:/automation/Job%20Applied/backend/app/services/automation_service.py)
*   **Refactoring**: Refactored the single-pass HTML form-filler (`_get_single_pass_answers` method) to import the prompts module and fetch `system_msg` and `user_msg` templates dynamically.

---

## Verification Plan

### Automated Tests
*   Executed syntax check commands to compile `app/ai/prompts.py`:
    `.\venv\Scripts\python.exe -c "import app.ai.prompts; print('Imports compiled successfully!')"`
*   Executed direct hermes extraction test script:
    `.\venv\Scripts\python.exe scratch\test_hermes_direct.py`
*   Verified that imports compile correctly, settings initialize properly, database connections succeed, and the refactored prompts route correctly to the Groq/OpenRouter client.
