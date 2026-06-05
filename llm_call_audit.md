# LLM Call Audit Report

This document presents a comprehensive technical audit of all Large Language Model (LLM) calls and integrations within the **AI Job Automation Platform**.

---

## 1. Executive Summary & Configuration

The application implements a centralized agent-based architecture around the `HermesAgent` class to handle LLM interactions. LLM endpoints are primarily powered by **OpenRouter** or **Groq**, depending on the environment configuration, and are accessed using the `openai` Python SDK (via `AsyncOpenAI`).

### Configuration Settings
All credentials and active models are loaded from `app/core/config.py` (which reads from `backend/.env`):
*   **OpenRouter API Key (`OPENAI_API_KEY`)**: Used for routing requests to models via OpenRouter (defaults to base URL `https://openrouter.ai/api/v1`).
*   **Groq API Key (`GROQ_API_KEY`)**: Used if a Groq-compatible model is configured (defaults to base URL `https://api.groq.com/openai/v1`).
*   **Active Model (`OPENAI_MODEL`)**: Defined as `llama-3.1-8b-instant` in `.env`, falling back to `openai/gpt-oss-20b` in `config.py` if missing.
*   **Tinyfish Key (`TINYFISH_API_KEY`)**: Configured but currently unused in codebase logic.

---

## 2. Core LLM Operations Audit

The table below lists all execution paths in the codebase that invoke an LLM.

| ID | Location | Trigger Endpoints / Methods | Configured Model | Purpose & Scope | Response Type & Fallback Mode |
|---|---|---|---|---|---|
| **1** | `hermes.py` / `extract_profile_data` | `POST /api/v1/resumes/upload`<br>`POST /api/v1/resumes/save-text` | `llama-3.1-8b-instant` (OpenRouter/Groq) | Extracts contact, skills, experience, education, certs, and languages from raw resume text. | **JSON Object**.<br>If `llama-3.3` fails, retries with `llama-3.1-8b-instant`. On complete API failure, falls back to regex parser. |
| **2** | `automation_service.py` / `_get_single_pass_answers` | `POST /api/v1/jobs/apply/{job_id}` | `llama-3.1-8b-instant` (OpenRouter/Groq) | Analyzes a minified HTML form alongside user profile and resume to output form answers. | **JSON Object**.<br>Returns `[]` if LLM client is missing or call fails. |
| **3** | `hermes.py` / `analyze_job` | `enrich_job_data` (Background Task)<br>`POST /api/v1/jobs/optimize-resume/{job_id}` | `llama-3.1-8b-instant` (OpenRouter/Groq) | Ranks resume-job alignment, outputs match score, and offers suggestions for tailoring. | **JSON Object**.<br>Falls back to Python Jaccard keyword matching on failure. |
| **4** | `hermes.py` / `calculate_match_score` | `enrich_job_data` (Background Task)<br>`scrape_jobs_for_new_resume`<br>`POST /api/v1/jobs/apply/{job_id}` | `llama-3.1-8b-instant` (OpenRouter/Groq) | Provides a standalone numerical match score (0-100) between resume and job description. | **Plain Text (Numeric)**.<br>Returns `80` (or `75` if client missing) on failure. |
| **5** | `hermes.py` / `extract_job_details` | `enrich_job_data` (Background Task) | `llama-3.1-8b-instant` (OpenRouter/Groq) | Extracts skills and bulleted qualifications list from raw job descriptions. | **JSON Object**.<br>Falls back to capitalization regex-extractor on failure. |
| **6** | `hermes.py` / `optimize_resume` | *(Unused directly, available for resume tailoring)* | `llama-3.1-8b-instant` (OpenRouter/Groq) | Tailors resume sections for a job description while preserving all items and page density. | **JSON Object**.<br>Returns error message/dictionary on failure. |
| **7** | `hermes.py` / `get_search_suggestions` | `scrape_jobs_for_new_resume`<br>`GET /api/v1/resumes/suggestions` | `llama-3.1-8b-instant` (OpenRouter/Groq) | Analyzes candidate experience to suggest 5 relevant search terms for job hunting. | **JSON List**.<br>Falls back to `["Software Engineer", "Full Stack Developer", "Backend Developer"]`. |
| **8** | `hermes.py` / `generate_optimized_resume_for_role` | `POST /api/v1/resumes/optimize-preview` | `llama-3.1-8b-instant` (OpenRouter/Groq) | Tailors experience details and projects to fit specific role requirements within 2 pages. | **JSON Object**.<br>Returns error dictionary on failure. |
| **9** | `hermes.py` / `generate_cover_letter` | *(Unused directly, helper function)* | `llama-3.1-8b-instant` (OpenRouter/Groq) | Generates a tailored cover letter from job and resume details. | **Plain Text**.<br>Falls back to generic cover letter template string. |

---

## 3. Deep Dive Analysis of LLM Call Points

### 3.1 Extract Profile Data (`extract_profile_data`)
*   **File Context**: [app/ai/hermes.py (Line 468-652)](file:///d:/automation/Job%20Applied/backend/app/ai/hermes.py#L468-L652)
*   **Prompt Construction**: 
    *   Context is preprocessed using a local `ResumeCompressor` pipeline that removes boilerplate lines and Jaccard-duplicate bullets, shrinking the raw text context.
    *   Instructs the model to return a structured JSON representing user profiles containing contact info, skills, education, languages, certs, projects, and work experience.
    *   Rules explicitly command the model: *"List ONLY actual employment positions... Do NOT include personal projects... Do not invent data... Use null if missing."*
*   **JSON Schema**:
    ```json
    {
      "full_name": "string",
      "email": "string or null",
      "phone": "string or null",
      "current_location": "string or null",
      "linkedin_url": "string or null",
      "github_url": "string or null",
      "portfolio_url": "string or null",
      "summary": "2-3 sentence summary",
      "skills": ["string"],
      "work_experience": [
        {
          "company": "string",
          "role": "string",
          "start": "string",
          "end": "string",
          "description": "string"
        }
      ],
      "projects": [
        {
          "name": "string",
          "description": "string",
          "technologies": ["string"]
        }
      ],
      "total_years_experience": 0,
      "education": [
        {
          "degree": "string",
          "institution": "string",
          "year": "string",
          "field": "string"
        }
      ],
      "certifications": [
        {
          "name": "string",
          "issuer": "string",
          "year": "string or null"
        }
      ],
      "languages": ["string"]
    }
    ```
*   **Post-processing & Fallback**: 
    *   Filters out freelance/academic projects accidentally added by the LLM into `work_experience` and relocates them to `projects`.
    *   Overwrites the LLM's `total_years_experience` by calculating it programmatically via a date interval merger to prevent double-counting overlaps.
    *   If the primary model fails and it is a `llama-3.3` model, it falls back to a second call using `llama-3.1-8b-instant`.
    *   If all LLM calls fail, it utilizes a regex parser to pull name, email, phone, and profile summary.

### 3.2 Single-Pass Form Filler (`_get_single_pass_answers`)
*   **File Context**: [app/services/automation_service.py (Line 320-414)](file:///d:/automation/Job%20Applied/backend/app/services/automation_service.py#L320-L414)
*   **Prompt Construction**:
    *   System Prompt defines a job assistant persona that maps minified HTML to answers.
    *   User Message feeds three elements: truncated resume (first 5,000 chars), user profile JSON (which contains custom questionnaire answers), and minified HTML containing target `data-qa-idx` tags.
    *   Instructions command: Prioritize questionnaire answers; calculate tech experience by summing resume timeline details; map select/radio verbatim to HTML choices; set visa sponsorship options strictly (authorized -> Yes/true, sponsorship -> No/false); keep text replies to $\le 2$ sentences.
*   **JSON Schema**:
    ```json
    {
      "answers": [
        {
          "qa_idx": "string",
          "label": "string",
          "type": "text | select | radio | checkbox",
          "answer": "string",
          "selector": "string (CSS selector)"
        }
      ]
    }
    ```
*   **Fallback**: Returns an empty array `[]` on exceptions.

### 3.3 Semantic Job Matcher (`analyze_job`)
*   **File Context**: [app/ai/hermes.py (Line 135-201)](file:///d:/automation/Job%20Applied/backend/app/ai/hermes.py#L135-L201)
*   **Prompt Construction**: 
    *   Compares truncated Job Description (first 3000 chars) against Resume (first 30000 chars).
*   **JSON Schema**:
    ```json
    {
      "match_score": 75,
      "suggestions": ["suggestion 1", "suggestion 2", "suggestion 3"],
      "technical_alignment": "description string"
    }
    ```
*   **Fallback**: Performs local token intersection checks to generate a basic matching ratio:
    $$\text{score} = \min\left(98, \frac{\text{len}(\text{job\_keywords} \cap \text{resume\_keywords})}{\text{len}(\text{job\_keywords})} \times 100 + 20\right)$$
    Suggestions are populated using unmatched keywords from the job description.

### 3.4 Standalone Match Score (`calculate_match_score`)
*   **File Context**: [app/ai/hermes.py (Line 240-276)](file:///d:/automation/Job%20Applied/backend/app/ai/hermes.py#L240-L276)
*   **Prompt Construction**:
    *   Inputs: JD (first 1500 chars) and Resume (first 30000 chars).
    *   Commands the model to return *ONLY* a number between 0 and 100.
*   **Fallback**: Returns 80 on exception (or 75 if client is unconfigured).

### 3.5 Extract Job Details (`extract_job_details`)
*   **File Context**: [app/ai/hermes.py (Line 202-239)](file:///d:/automation/Job%20Applied/backend/app/ai/hermes.py#L202-L239)
*   **Prompt Construction**:
    *   Inputs: JD (first 3000 chars).
*   **JSON Schema**:
    ```json
    {
      "skills": "comma-separated top 8 technical skills",
      "requirements": "bulleted list of 3-5 key qualifications"
    }
    ```
*   **Fallback**: Returns list of all capitalized words (like programming languages / tools) from the description.

### 3.6 Resume Optimizations & Cover Letter Gen (`optimize_resume`, `generate_optimized_resume_for_role`, `generate_cover_letter`)
*   **File Context**: [app/ai/hermes.py (Line 277-467)](file:///d:/automation/Job%20Applied/backend/app/ai/hermes.py#L277-L467)
*   **Prompt Construction**:
    *   `optimize_resume` and `generate_optimized_resume_for_role` enforce executive resume writer personas.
    *   Rules: Maintain ATS-readable formatting (no tables, graphics, progress bars), preserve all items (zero data loss), and keep page density under 2 pages.
    *   Uses custom project extraction patterns to recover projects from malformed headings (e.g. `PRPROJECTS`).
*   **JSON Schema (`generate_optimized_resume_for_role`)**:
    ```json
    {
      "full_resume_text": "string",
      "ats_tips": ["string"],
      "optimized_skills": ["string"]
    }
    ```

### 3.7 Search Suggestions Generator (`get_search_suggestions`)
*   **File Context**: [app/ai/hermes.py (Line 333-368)](file:///d:/automation/Job%20Applied/backend/app/ai/hermes.py#L333-L368)
*   **Prompt Construction**:
    *   Analyzes candidate resume to generate exactly 5 targeted search terms for matching engines.
*   **JSON Schema**: Returns a JSON array of 5 strings (e.g., `["Software Engineer", "React Developer", ...]`).

---

## 4. Key Findings & Architectural Observations

### 4.1 Encapsulation Bypass
The automation form filling process in `automation_service.py` directly executes the raw OpenAI completions API:
```python
resp = await hermes_agent.client.chat.completions.create(...)
```
This bypasses the `HermesAgent` interface. For a clean, modular design, this logic should be encapsulated inside a dedicated method in `HermesAgent`, such as `generate_form_answers(...)`.

### 4.2 Local Preprocessing Strategy
The application makes clever use of a local custom preprocessor `ResumeCompressor` (written in Python utilizing `nltk`) *before* invoking `extract_profile_data`. By identifying and removing boilerplate phrases, deduplicating bullets, and selecting high-density content blocks, it significantly cuts token overhead while avoiding data loss prior to sending content to the LLM.

### 4.3 Key Configuration Fallbacks
Most LLM calls have structured fallbacks (e.g. keywords analysis, regex, or static defaults) that guarantee the application remains functional even if API keys expire or the LLM providers fail.
