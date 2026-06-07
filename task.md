# AI & Automation Backend Tasks

This file tracks all tasks, optimizations, and TODOs identified in the [AI_AUTOMATION_BACKEND_AUDIT.md](file:///d:/automation/Job%20Applied/AI_AUTOMATION_BACKEND_AUDIT.md).

## P0 (Critical) — Cross-Platform Reliability & Cost Reduction
- [x] **Consolidate Job Enrichment Prompts**: Merge `calculate_match_score` and `extract_job_details` into `analyze_job` to reduce LLM calls by 66% and token usage by ~51%.
- [x] **Fix Windows-Specific subprocess Calls**: Replace PowerShell process termination (`Stop-Process`) with a cross-platform Python-native solution using `psutil`.
- [x] **Move Browser Lock Cleanup to Startup**: Pre-emptively delete Chromium `SingletonLock` on startup in `apply_to_job` and `launch_login_browser`.
- [x] **Support Headless Mode in Production**: Add `HEADLESS` environment variable, configure it in `config.py`/`Dockerfile`, and pass it to Playwright browser context launch.

## P1 (Important) — Architecture & Performance
- [x] **In-Process Background Task Execution (No Celery/Redis)**: Run all automation and enrichment tasks in-process utilizing FastAPI's `BackgroundTasks` thread pool, avoiding Redis/Celery operational overhead per user request.
- [x] **Add Missing DB Indexes**: Add database indexes to foreign keys (`user_id`, `job_id`) in the `Application` and `Resume` models to prevent slow sequential scans as the tables grow.
- [x] **Clean Platform Disconnections**: Ensure platform disconnection routes correctly clean up browser user-data directories and platform status marker files.

## P2 (Future) — Advanced Optimizations
- [ ] **Implement Question-Answer Memory Bank**: Save successful application form questionnaire answers to a new `question_bank` database table and perform local semantic matching (TF-IDF/RapidFuzz) before querying LLMs.
- [ ] **Add Redis API Search Caching**: Cache JSearch API queries (e.g. `jobs:search:query_location`) in Redis for 2 hours to protect third-party API limits and speed up dashboard reloads.
- [ ] **Strict Structured JSON Format Enforcement**: Upgrade LLM calls in `hermes.py` to use OpenAI/Groq's native structured outputs (e.g., passing Pydantic models in `response_format` schemas) to prevent structure violations.

## Additional Code Cleanup & Security Improvements
- [ ] **Optimize Search Suggestions Input**: Retrieve search suggestions using the extracted profile's `desired_job_titles` rather than sending the entire uncompressed 30k resume text to LLM.
- [ ] **Optimize Form Filling Input**: Remove the raw 5000-character `resume_text` parameter from the form-filling prompt, relying solely on structured `profile_data` and HTML context to save ~1,300 tokens per step.
- [ ] **Clean Cover Letter Dead Code**: Clean/remove unused cover letter generation code in `hermes.py` or expose it via a new `/resumes/{id}/cover-letter` endpoint.
- [ ] **Decouple `AutomationService`**: Split the large `automation_service.py` file:
  - Move page utility functions (e.g. `_wait_for_page_settle`, `_get_active_modal`) to `app/services/automation/utils.py`.
  - Move HTML clean and tagging functions into a separate parser class.
- [ ] **Improve Token Security**: Shorten access token expiration (currently 7 days) and implement standard HTTP-only cookie refresh flows. Remove default PostgreSQL passwords from default configuration files.
