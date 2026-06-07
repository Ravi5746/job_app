# 🔍 Backend System Audit Report

**Date:** June 7, 2026  
**Audited By:** AI Systems Audit  
**Codebase:** AI Job Application Automation Platform

---

## Executive Summary

A full technical audit of the backend codebase has identified **5 Critical, 8 High, 7 Medium, and 5 Low severity issues**. The most critical concerns are the lack of user session isolation in the Playwright browser profile directories (enabling user-to-user session hijacking), database schema violations where job states and tailored resumes are stored globally and overwrite other users' data, and unprotected API endpoints (specifically `DELETE /api/v1/jobs/clear-all`) that can delete all data without authentication. Immediate action items include refactoring browser workspace resolution, implementing correct authentication middleware on all routes, and decoupling the shared `jobs` database table into a proper user-specific `applications` table.

---

## Issues by Severity

### 🔴 Critical Issues

#### [CRIT-001] Missing Authentication on Core API Endpoints
- **File:** `backend/app/routes/jobs.py` (lines 86, 118, 142, 160, 172, 328, 332)
- **Description:** Core endpoints in the jobs router (search, list, read, create, update, delete, and delete all) completely lack the `Depends(get_current_user)` dependency check. 
- **Impact:** Any anonymous user or client can query, modify, delete individual jobs, or call the `/clear-all` endpoint to wipe the entire database table without credentials.
- **Root Cause:** Omission of authentication middleware dependencies on the router or individual routes.
- **Fix:** Secure all routes by adding the `current_user` dependency:
  ```python
  @router.delete("/clear-all")
  def clear_all_jobs(
      db: Session = Depends(get_db),
      current_user: UserModel = Depends(get_current_user)
  ):
  ```

#### [CRIT-002] Multi-User Browser Session Overwrite (No Sandbox Isolation)
- **Files:** `backend/app/services/automation_service.py` (lines 580, 885), `backend/app/routes/settings.py` (lines 51, 80)
- **Description:** Browser contexts and settings marker files resolve to a single shared folder `settings.USER_DATA_DIR` without appending the `user_id`.
- **Impact:** 
  - **Session Hijacking:** When User A connects their LinkedIn account, User B automatically inherits User A's active session, allowing User B to perform applications as User A.
  - **Concurrency Crash:** Multiple users running applications concurrently will hit locking errors on the shared Chromium folder, causing browser crashes.
- **Root Cause:** Global session path resolution lacking user-level directory partitioning.
- **Fix:** Append the authenticated `user_id` to the session directories:
  ```python
  user_data_dir = os.path.join(settings.USER_DATA_DIR, str(user_id), platform_name)
  ```

#### [CRIT-003] Shared Server Process Termination Crashes Concurrent Users
- **File:** `backend/app/services/automation_service.py` (lines 616-629)
- **Description:** When browser initialization fails due to directory locks, the application uses `psutil` to iterate over all active processes on the host and kill all processes containing `chrome` or `chromium` in their executable path.
- **Impact:** A browser crash for User A will force-kill all active web browsers of all other users running applications concurrently on the same server instance.
- **Root Cause:** Global process-level cleanup logic instead of targeted PID-based session termination.
- **Fix:** Store individual subprocess PIDs when launching Playwright and call `.kill()` only on the specific PID linked to that task, or run user tasks inside isolated sandboxes.

#### [CRIT-004] Data Overwriting and Lack of Database Scoping on Job Listings
- **File:** `backend/app/routes/jobs.py` (lines 346, 387), `backend/app/models/job.py`
- **Description:** The resume tailoring results, match scores, and application status are stored directly on the shared `Job` model instead of the user's `Application` model.
- **Impact:** Since jobs are global and shared, when User A tailoring for a job executes, it overwrites the tailored resume, score, and applied status of User B for that same job record.
- **Root Cause:** Missing schema decoupling where application status and tailoring are improperly bound to the shared job board metadata instead of the individual application relationship.
- **Fix:** Remove columns `tailored_resume`, `match_score`, `match_suggestions`, and `status` from `Job` table. Implement writes and reads for these fields on the `applications` table.

#### [CRIT-005] Missing Rollback Logic on Failed Background Task DB Sessions
- **Files:** `backend/app/routes/jobs.py` (line 71), `backend/app/routes/resume.py` (line 144)
- **Description:** The background tasks `enrich_job_data` and `scrape_jobs_for_new_resume` instantiate independent database sessions `db = db_session_factory()`. In the case of exceptions during transactions, the code logs the error but does not call `db.rollback()`.
- **Impact:** Transaction state pollution, active database locks remain unreleased, and connection pool exhaustion, leading to eventual database unavailability.
- **Root Cause:** Missing transaction safety code in database context error handlers.
- **Fix:** Ensure a rollback is always executed in the exception block:
  ```python
  except Exception as e:
      db.rollback()
      logger.error(...)
  ```

---

### 🟠 High Issues

#### [HIGH-001] Browser Automation Running Synchronously in API Request Lifecycle
- **File:** `backend/app/routes/jobs.py` (line 400)
- **Description:** The `/apply/{job_id}` endpoint awaits `automation_service.apply_to_job` inside the request handler. This starts a browser session that runs for 60 to 120 seconds.
- **Impact:** Causes immediate API gateway timeouts, event loop blocking, server thread exhaustion, and bad UX as connection drops.
- **Root Cause:** Blocking heavy browser automation running inside the request-response thread instead of executing via background tasks.
- **Fix:** Delegate applications to an asynchronous task manager (e.g. Celery or a background queue) and return a task status token immediately.

#### [HIGH-002] Synchronous Blocking API Calls inside Async FastAPI Routes
- **File:** `backend/app/routes/jobs.py` (lines 185-325)
- **Description:** Route `search_external_jobs` is defined as `async def` but executes blocking synchronous HTTP network calls (like `scraper_service.search_jobs` and `search_linkedin_guest` via `requests`) and database commits.
- **Impact:** Blocks the FastAPI async event loop, freezing all incoming request processing for all connected clients.
- **Root Cause:** Invoking synchronous libraries inside an asynchronous routine without thread-pool offloading.
- **Fix:** Either run these routes as standard sync `def` functions, use `anyio.to_thread.run_sync`, or migrate requests to `httpx.AsyncClient`.

#### [HIGH-003] External API Invocation Lacks Request Timeout Configuration
- **File:** `backend/app/services/scraper_service.py` (lines 24, 37)
- **Description:** The GET queries to the external JSearch RapidAPI service do not specify a timeout parameter.
- **Impact:** If the external API hangs, the request hangs indefinitely, blocking resources and leading to thread pool starvation.
- **Root Cause:** Omission of standard request connection and read timeouts.
- **Fix:** Add a strict timeout parameter:
  ```python
  response = requests.get(self.url, headers=self.headers, params=querystring, timeout=10.0)
  ```

#### [HIGH-004] Core Applications Relationship and History Table is Unused
- **Files:** `backend/app/routes/applications.py`, `backend/app/models/application.py`
- **Description:** The applications route router contains zero endpoints, and the `Application` database model is never written to or tracked in the application service flow.
- **Impact:** Complete failure to log user application history, notes, or dates, leaving the core application status feature unimplemented.
- **Root Cause:** Abandoned feature implementation.
- **Fix:** Refactor `/apply` to create an `Application` entry in the DB, and add API endpoints to list and view applications.

#### [HIGH-005] Uploaded File Validation Relies Solely on Extension Checks
- **File:** `backend/app/routes/resume.py` (line 157)
- **Description:** The pdf format validator checks `if not file.filename.endswith('.pdf'):` instead of validating file signatures.
- **Impact:** Allows malicious users to upload scripts or executables renaming them as `.pdf` files, potentially leading to remote code execution (RCE) via parsing bugs in `PdfReader`.
- **Root Cause:** Fragile filename-based verification instead of mime-type or header content analysis.
- **Fix:** Inspect the first 4 bytes of the file for the PDF signature `%PDF-` prior to saving.

#### [HIGH-006] Dangling Temp Files on Resume Processing Failure
- **File:** `backend/app/routes/resume.py` (lines 174-241)
- **Description:** The uploaded resume file is saved to the filesystem before parsing text. If PDF reading fails, the route exits with a 500 error but does not delete the saved file.
- **Impact:** Filesystem pollution and rapid disk capacity exhaustion from invalid uploads.
- **Root Cause:** Missing cleanup handlers in the error capture block.
- **Fix:** Implement deletion in the exception branch:
  ```python
  except Exception as e:
      if os.path.exists(file_path):
          os.remove(file_path)
      raise HTTPException(...)
  ```

#### [HIGH-007] Production Docker Container Module Path Setup Failure
- **File:** `backend/Dockerfile` (line 18)
- **Description:** The Dockerfile starts the backend using the command `CMD ["uvicorn", "main:app", ...]`.
- **Impact:** Since the code is copied inside `/app`, uvicorn fails to locate `main.py` directly, crashing with `ModuleNotFoundError: No module named 'main'`.
- **Root Cause:** Mismatch in module paths inside the container file tree.
- **Fix:** Correct the command to `uvicorn app.main:app`.

#### [HIGH-008] Missing Browser Binary Dependencies in Container Image
- **File:** `backend/Dockerfile`
- **Description:** The Docker file installs python requirements but does not install Playwright system dependencies or browser binaries.
- **Impact:** Playwright throws execution errors on launch due to missing Chromium binaries and required Linux shared libraries.
- **Root Cause:** Missing docker image setup instructions for chromium execution.
- **Fix:** Add apt library dependency installs and browser setup calls:
  ```dockerfile
  RUN playwright install chromium
  RUN playwright install-deps
  ```

---

### 🟡 Medium Issues

#### [MED-001] Global Document Query Check in Scoped Modal Validation
- **File:** `backend/app/services/automation/agent/dom_layer.py` (line 330)
- **Description:** The `check_required_empty` function executes `document.querySelectorAll('[required]')` instead of limiting searches to the active modal workspace context.
- **Impact:** Reports validation errors and blocks form submission for fields located entirely outside the visible modal (e.g. underlying pages).
- **Root Cause:** Query selectors scoping globally to `document` instead of restricting search elements to the active modal locator.
- **Fix:** Restrict check queries:
  ```javascript
  const required = (modal || document).querySelectorAll('[required], [aria-required="true"]');
  ```

#### [MED-002] LinkedIn Guest Scraper Relies on Fragile HTML Parsing Regex
- **File:** `backend/app/services/scraper_service.py` (lines 56, 81-116)
- **Description:** LinkedIn guest scraper parses search listings by executing multiple regular expression searches over raw HTML tags.
- **Impact:** Breaks silently and returns empty lists or malformed text whenever LinkedIn changes its markup or CSS classes.
- **Root Cause:** Parsing XML/HTML structures using regular expressions instead of structured selector patterns.
- **Fix:** Migrate parsing logic to BeautifulSoup CSS selector calls.

#### [MED-003] Omission of Pydantic Schema Validation on AI Responses
- **File:** `backend/app/ai/hermes.py` (line 168)
- **Description:** Parse results from OpenRouter/Groq endpoints are loaded using `json.loads` and accessed directly without validate checks against a schema library.
- **Impact:** Missing keys or type mismatches from LLM outputs cause unhandled runtime `KeyError` exceptions.
- **Root Cause:** Missing validator checks for AI JSON payloads.
- **Fix:** Standardize structured extraction check using Pydantic models.

#### [MED-004] Missing Database Index on `jobs.url`
- **File:** `backend/app/models/job.py` (line 13)
- **Description:** The `url` field in the jobs table lacks database index annotations.
- **Impact:** Running duplication checks for each scraped card executes full table scans, heavily slowing database performance as record counts increase.
- **Root Cause:** No index decoration on queries.
- **Fix:** Add database indexing settings to the `url` column definition.

#### [MED-005] False Positives in Deterministic Form pre-filling
- **File:** `backend/app/services/automation/agent/deterministic_fill.py` (lines 35-48)
- **Description:** Regex matches on combined name, id, and label attributes can map personal user values into company/reference fields.
- **Impact:** Pre-fills contact details like personal email or phone into alternative contact slots (e.g., employer email).
- **Root Cause:** Loose search patterns mapping attributes.
- **Fix:** Restrict matches, filtering out keywords like `employer_`, `company_`, or `ref_`.

#### [MED-006] Side-Effects on GET Routes (DB Deletion Tasks)
- **File:** `backend/app/routes/jobs.py` (lines 94, 126)
- **Description:** The GET endpoints for job list and db searches run cleanup routines deleting expired rows from the database.
- **Impact:** Side-effect mutations on read operations reduce route performance and cause database write locking conflicts.
- **Root Cause:** Executing cleanup transactions during GET api request lifecycles.
- **Fix:** Relocate database sweeps to a cron or worker task loop.

#### [MED-007] Token Telemetry Declared but Not Logged
- **File:** `backend/app/services/automation/agent/state.py` (lines 34-35)
- **Description:** The `input_tokens` and `output_tokens` telemetry attributes are never populated during agent operations.
- **Impact:** Prevents cost tracking and monitoring of LLM usage per application.
- **Root Cause:** Telemetry variables left unlinked from API calls.
- **Fix:** Populate fields from the token metadata returned in LLM client responses.

---

### 🔵 Low Issues / Code Quality

#### [LOW-001] Unused Duplicate Auth Code
- **File:** `backend/app/middleware/auth.py`
- **Description:** The entire middleware file defines a duplicate authentication utility that is never imported or referenced by the codebase.
- **Fix:** Safely delete `backend/app/middleware/auth.py` to keep the workspace clean.

#### [LOW-002] Inconsistent Error Response Formats
- **Files:** `backend/app/routes/jobs.py`, `backend/app/routes/resume.py`
- **Description:** Some routes return error dict structures like `{"status": "error", "message": ...}` while others raise native FastAPI `HTTPException`.
- **Fix:** Refactor error logic to standardize on raising `HTTPException` globally.

#### [LOW-003] Confusing Non-Python Dependency in Pip Requirements
- **File:** `backend/requirements.txt` (line 14)
- **Description:** The package dependency file lists `axios` (a JavaScript client library).
- **Fix:** Remove the package entry from the python requirements list.

#### [LOW-004] Hardcoded Platform and Control Loop Magic Constants
- **Files:** `backend/app/services/automation_service.py`, `backend/app/services/automation/linkedin_handler.py`
- **Description:** Constants (like timeout counts, sleep intervals, login loops, URLs) are defined inline within handlers.
- **Fix:** Move values to a global config setting.

#### [LOW-005] Complete Absence of Unit and Integration Tests
- **Description:** The project lacks any automated test suites, scripts, or mocked configurations.
- **Fix:** Establish testing directories and configure pytest mocks.

---

## Gaps by System Area

### API Layer Gaps
- **Missing Pagination:** Endpoints returning lists of records could experience query timeouts when database rows grow large.
- **No Global Rate Limiter:** Exposed endpoints can be abused without rate caps.
- **Empty Applications Endpoint:** Missing endpoints to query and filter job-to-user application maps.

### AI/LLM Engine Gaps
- **Lack of Output Schema Enforcement:** OpenRouter models run without structured JSON schema restrictions.
- **Prompt Compaction Needed:** Resume summaries parse raw text repeatedly, wasting token budgets.
- **Missing Token Logging:** No telemetry logs for LLM operation costs.

### Browser Automation Gaps
- **Shared Working Profile:** Lack of isolation prevents safe parallel execution.
- **Stale Browser Cleanup:** Kills active chrome process pipelines globally across the server.
- **Uncontrolled Loops on Failure:** Will continue to retry blocked forms through blind page advances.

### Database Layer Gaps
- **Improper Table Normalization:** User specific job states are persisted globally on the jobs table.
- **Missing Indexes:** Index missing on `jobs.url` query checks.
- **Manual Migration Management:** Raw migrations are maintained in standalone scripts instead of a system tool like Alembic.

### Infrastructure Gaps
- **Incomplete Docker Configuration:** Production docker container image will fail to compile and run Playwright.
- **Unused Worker Queues:** Background workers are configured but ignored, overloading API threads.

---

## Missing Features (Not Bugs — Just Absent)

| Missing Feature | Area | Why It Matters | Complexity to Add |
|---|---|---|---|
| Celery Background Task Queue | Infrastructure | Prevents web server crash and timeout errors on long application pipelines. | Medium |
| Question-Answer Memory Bank | Browser Automation | Caches input entries, avoiding redundant AI requests and lowering token costs. | Medium |
| Alembic Migrations | Database Layer | Provides structured migration tracking and automatic database schema changes. | Low |
| Anti-Captcha Service Integration | Browser Automation | Resolves Cloudflare and Captcha challenges without manual intervention. | High |

---

## Risk Matrix

| Issue ID | Severity | Likelihood | Impact | Priority |
|---|---|---|---|---|
| CRIT-001 | Critical | High | Data Loss / Unauthorized Access | P0 |
| CRIT-002 | Critical | High | Session Hijacking / Privacy Leak | P0 |
| CRIT-003 | Critical | Medium | Denial of Service (Server Crashes) | P0 |
| CRIT-004 | Critical | High | Data Corruption / Overwritten States | P0 |
| CRIT-005 | Critical | High | DB Connection Exhaustion (Crash) | P0 |
| HIGH-001 | High | High | Server Hangs / Request Timeout | P1 |
| HIGH-002 | High | High | Event Loop Freeze (Concurrency Stop) | P1 |
| HIGH-003 | High | Medium | Worker Thread Exhaustion | P1 |
| HIGH-007 | High | High | Build & Deploy Failure (Prod Crash) | P1 |
| HIGH-008 | High | High | Playwright Launch Failure | P1 |

---

## Recommended Fix Order

1. **CRIT-001 (Protect APIs)** — Secure exposed jobs paths immediately to prevent unauthorized data manipulation.
2. **CRIT-002 (Browser Isolation)** — Sandbox browser profile namespaces by user ID to stop privacy leaks.
3. **CRIT-004 (Decouple Job State)** — Migrate job status/tailored resumes to application tables so users don't overwrite each other.
4. **CRIT-005 (Transaction Rollback)** — Add rollback calls to background errors to stop database pool exhaustion.
5. **HIGH-001 / HIGH-002 (Queue Tasks / Unblock event loop)** — Shift long browser operations to Celery worker threads and unblock FastAPI endpoints.
6. **HIGH-007 / HIGH-008 (Docker/Playwright Fixes)** — Adjust production docker imports and install Playwright requirements.
7. **CRIT-003 (Process Control)** — Revise browser termination commands to target specific process IDs instead of global kills.
8. **HIGH-003 (HTTP Timeout)** — Force timeouts on API scrapes to prevent thread freezes.
9. **MED-004 (DB Indexes)** — Add db indexing to job URLs to speed up deduplication lookups.
10. **MED-001 (Modal Scope)** — Scoping JS input validation to modal boundaries to resolve premature button blocking.

---

## Audit Notes

1. **Jobs Table Scoping:** Verify if the business design is intended to have jobs shared across all users (like a shared job board) or if jobs are completely private per user. If shared, moving match scores and tailored resumes to the `applications` relation is mandatory. If private, the `jobs` table itself must have a `user_id` foreign key.
2. **Celery worker usage:** Confirm if Celery was bypassed during staging due to broker costs or implementation speed, as activating Celery tasks requires a broker (like Redis or RabbitMQ) added to the Docker environment.
3. **Indeed Frame Handling:** Indeed frame paths sometimes change dynamically; check if there is an alternative direct navigate path for indeed easy-apply targets to bypass framing entirely.
