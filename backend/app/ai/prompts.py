import json
from typing import Dict, Any

def get_analyze_job_prompt(job_description: str, resume_content: str) -> str:
    """
    Generate prompt for semantic job description and resume comparison,
    including key skills and requirements extraction.
    """
    return f"""
    You are a professional HR recruiter, ATS expert, and technical career coach.
    Analyze the following Job Description and compare it with the User's Resume.
    
    JOB DESCRIPTION:
    {job_description[:3000]}
    
    USER RESUME:
    {resume_content[:30000]}
    
    Provide your analysis in JSON format with exactly these keys:
    "match_score": (integer between 0 and 100),
    "suggestions": (list of 3 specific things to improve in the resume for this job),
    "technical_alignment": (short description of how skills align),
    "skills": (comma-separated list of top 8 technical skills extracted from the job description),
    "requirements": (bulleted list of 3-5 key qualifications extracted from the job description)
    """


def get_extract_job_details_prompt(job_description: str) -> str:
    """
    Generate prompt to extract technical skills and key requirements from a job description.
    """
    return f"""
    Extract the technical skills and key requirements from this job description.
    
    JOB DESCRIPTION:
    {job_description[:3000]}
    
    Provide JSON with:
    "skills": (comma-separated list of top 8 technical skills),
    "requirements": (bulleted list of 3-5 key qualifications)
    """


def get_calculate_match_score_prompt(job_description: str, resume_content: str) -> str:
    """
    Generate prompt to calculate a simple match score between a job and resume.
    """
    return f"""
    Compare this resume to the job description and provide a match score from 0 to 100.
    
    JOB:
    {job_description[:1500]}
    
    RESUME:
    {resume_content[:30000]}
    
    Provide ONLY the number (0-100).
    """


def get_optimize_resume_prompt(job_description: str, resume_content: str) -> str:
    """
    Generate prompt to tailor/optimize resume sections for a specific job.
    """
    return f"""
    You are a World-Class Executive Career Coach and ATS (Applicant Tracking System) Expert.
    Your mission is to perform a 'Precision Tailoring' of the user's resume to the provided Job Description.

    STRICT ARCHITECTURAL REQUIREMENTS:
    1. MANDATORY SECTIONS: You MUST include Header, Professional Summary, Core Competencies, Professional Experience, Projects, Education, and Certifications.
    2. ZERO DATA LOSS: Never delete a company, a project, a certification, or an educational degree. You are optimizing content, not reducing career history.
    3. PAGE DENSITY PRESERVATION: You must maintain the original document's length. If the original content suggests a 2-page resume, your output must provide enough detail and spacing to fill 2 pages. Do not condense a 2-page career into a 1-page summary.
    4. CONTACT INTEGRITY: Keep Name, Phone, Email, LinkedIn, and GitHub links exactly as they appear.

    OPTIMIZATION STRATEGY:
    - PROFESSIONAL SUMMARY: Rewrite to highlight the most relevant skills/years of experience matching the JD.
    - EXPERIENCE & PROJECTS: Rewrite bullet points to lead with strong Action Verbs and include quantifiable results. Infuse the JD's 'Required Skills' and 'Key Keywords' naturally into these bullets.
    - CORE COMPETENCIES: Re-order and update the technical skills list to prioritize what the JD is looking for.
    - FORMATTING: Use clear, all-caps headers for sections (e.g., PROFESSIONAL EXPERIENCE). Use standard bullet points (•).

    JOB DESCRIPTION:
    {job_description[:1800]}
    
    USER'S ORIGINAL RESUME (Raw Text):
    {resume_content[:30000]}
    
    Provide the response in JSON format:
    {{
        "full_resume_text": "The entire professionally tailored resume here...",
        "ats_tips": ["3-5 high-level strategy tips specifically for this JD"],
        "match_score": 85,
        "match_suggestions": "Brief explanation of why this score was given and what key keywords were added."
    }}
    """


def get_search_suggestions_prompt(resume_content: str) -> str:
    """
    Generate prompt for job title search suggestions based on resume.
    """
    return f"""
    Based on this resume, suggest 5 targeted job titles or search queries I should use to find relevant jobs.
    
    RESUME:
    {resume_content[:30000]}
    
    Provide a JSON list of 5 strings.
    """


def get_generate_optimized_resume_for_role_prompt(target_role: str, resume_content: str, job_description: str = "") -> str:
    """
    Generate prompt to optimize a resume specifically for a target role and job description.
    """
    return f"""
    You are an expert ATS Resume Writer, Recruiter, Hiring Manager, and Career Optimization AI.
    Your task is to generate a highly ATS-optimized, recruiter-friendly, and modern professional resume customized for the user's target role, industry, experience level, and (optional) job description.

    TARGET ROLE: "{target_role}"
    JOB DESCRIPTION (IF PROVIDED):
    {job_description or "None provided"}

    PRIMARY GOAL:
    Generate a resume that:
    - Maximizes ATS compatibility (Workday, Greenhouse, Lever, Taleo, BambooHR, Naukri)
    - Improves recruiter shortlisting probability
    - Aligns with modern hiring standards (2026)
    - Maintains professional credibility
    - Achieves high keyword relevance without keyword stuffing

    STRICT ARCHITECTURAL & ATS RULES:
    1. ATS-READABLE FORMATTING ONLY: Avoid tables, graphics, icons, charts, ratings, progress bars, multi-column layouts, or decorative formatting. Use standard uppercase section headings:
       SUMMARY
       EXPERIENCE
       PROJECTS
       SKILLS
       EDUCATION
       CERTIFICATIONS
    2. ZERO DATA LOSS: Never delete any company, project, certification, or educational degree. Do not remove any section. You are enhancing the content, not reducing career history. Ensure that if the original resume lists projects, they are fully retained and optimized under the 'PROJECTS' section.
    3. PAGE LENGTH PRESERVATION: The generated resume MUST NOT exceed 2 pages. Tailor the depth of descriptions and bullet points so the content is dense and fits perfectly within 1 or 2 pages when printed (typically 750 to 900 words maximum overall). Ensure that final sections like 'EDUCATION' and 'CERTIFICATIONS' do not overflow to a blank 3rd page.
    4. CONTACT INTEGRITY: Keep all personal contact information (Name, Phone, Email, LinkedIn, GitHub links) exactly as they appear.
    5. PROJECT EXTRACTION & TYPO FIXING: Look closely for any projects listed in the original resume (even under misspelled or malformed section headers like 'PRPROJECTS' or 'PROJECTS'). You MUST extract all projects from that section (such as 'AutomationOwl', 'YogLiving', 'Payroll & ERP Management System') and rewrite them under a standard 'PROJECTS' section in the optimized output.

    DYNAMIC ROLE & KEYWORD ADAPTATION:
    - PROFESSIONAL SUMMARY: Write a concise and impactful professional summary (3-4 sentences) that immediately aligns with the target role, highlights major strengths, and naturally incorporates high-value keywords.
    - EXPERIENCE WRITING: Every experience bullet point must contain a strong action verb + technology/tool/process used + business outcome or measurable impact.
      Preferred format: [Action Verb] + [Skill/Technology/Process] + [Measurable Impact].
      Examples:
      * Improved application performance by 40% using Redis caching and query optimization.
      * Increased lead conversion rates by 25% through targeted email marketing campaigns.
      * Reduced operational costs by automating reporting workflows using Python and SQL.
      Avoid generic bullets like "Responsible for development", "Worked on projects", or "Assisted team".
    - SKILLS OPTIMIZATION: Organize skills by category. Prioritize the most relevant technical and professional skills first. Include keywords naturally and match terminology from the provided job description when appropriate.
    - PROJECTS OPTIMIZATION: Demonstrate practical skills, show measurable impact, list tools/technologies used, and reflect real-world applications.

    USER'S ORIGINAL RESUME:
    {resume_content[:30000]}
    
    Provide the response in JSON format:
    {{
        "full_resume_text": "The entire optimized resume here...",
        "ats_tips": ["3-5 high-level strategy tips specifically for a {target_role} resume based on the job description"],
        "optimized_skills": ["List of key technical skills added or emphasized"]
    }}
    """


def get_generate_cover_letter_prompt(job_title: str, company: str, resume_content: str) -> str:
    """
    Generate prompt for tailored cover letter generation.
    """
    return f"Generate a tailored cover letter for a {job_title} role at {company} based on this resume: {resume_content[:30000]}"


def get_extract_profile_data_prompt(resume_content: str) -> str:
    """
    Generate prompt to extract structured profile data from compressed resume text.
    """
    return f"""
    Extract ALL of the following structured data from this resume.
    Be thorough — scan the entire document including headers, footers, and all sections.

    RESUME:
    {resume_content}

    Return a JSON object with EXACTLY these keys:
    {{
        "full_name": "string",
        "email": "string or null",
        "phone": "string or null",
        "current_location": "string or null",
        "linkedin_url": "string or null",
        "github_url": "string or null",
        "portfolio_url": "string or null (any other website/portfolio link)",
        "summary": "2-3 sentence professional summary of the candidate",
        "skills": ["list", "of", "technical", "and", "professional", "skills"],
        "work_experience": [
            {{
                "company": "Company Name",
                "role": "Job Title",
                "start": "MMM YYYY or YYYY",
                "end": "MMM YYYY or Present",
                "description": "1-2 sentence summary of responsibilities"
            }}
        ],
        "projects": [
            {{
                "name": "Project Name",
                "description": "1-2 sentence summary of what was built and technologies used",
                "technologies": ["list", "of", "technologies", "used"]
            }}
        ],
        "total_years_experience": 0,
        "education": [
            {{
                "degree": "Degree Name",
                "institution": "University/College Name",
                "year": "Graduation Year",
                "field": "Field of Study"
            }}
        ],
        "certifications": [
            {{
                "name": "Certification Name",
                "issuer": "Issuing Organization",
                "year": "Year or null"
            }}
        ],
        "languages": ["English", "Hindi"]
    }}

    RULES:
    - work_experience: List ONLY actual employment positions, internships, or professional roles at companies/organizations. Do NOT include personal projects, academic projects, side projects, or freelance projects here; instead, put those in the "projects" section.
    - projects: List personal, academic, open-source, or freelance projects.
    - total_years_experience: Calculate by summing work experience durations. Return as integer.
    - skills: Include ALL technical skills, tools, frameworks, and languages mentioned anywhere.
    - If a field cannot be found, use null for strings, empty array for lists, 0 for numbers.
    - Do NOT invent data that is not in the resume.
    """


# --- Automation Service (Form Filling) Prompts ---

SINGLE_PASS_FORM_SYSTEM_MSG = (
    "You are an expert job application assistant. "
    "Analyze the minified HTML form, matching user profile and resume, then answer every form field. "
    "Respond ONLY with a valid JSON object containing an 'answers' key mapping to an array of objects "
    "— no markdown, no preamble, no explanation."
)


def get_single_pass_answers_user_msg(resume_text: str, profile_data: Dict[str, Any], html_content: str) -> str:
    """
    Generate prompt user message for single pass job application form filling.
    """
    profile_data_json = json.dumps(profile_data, indent=2)
    resume_text_clean = resume_text[:5000] if resume_text else 'Not available'
    return f"""You are an expert Resume-to-Job-Application Form Mapping Engine.

### INPUTS

**RESUME (PDF Extracted Text)**
{resume_text_clean}

**USER PROFILE**
{profile_data_json}

**FORM HTML (Minified with data-qa-idx)**
{html_content}

### TASK

Analyze the HTML and identify **every interactive form element containing a `data-qa-idx` attribute**.

Using ONLY information from:

1. USER PROFILE
2. RESUME
3. Existing field values in HTML

Generate a JSON response:

```json
{{
  "answers": [
    {{
      "qa_idx": "1",
      "label": "Question text",
      "type": "text|textarea|select|radio|checkbox",
      "answer": "value",
      "selector": "unique css selector"
    }}
  ]
}}
```

### STRICT RULES (NO HALLUCINATION)

1. Use USER PROFILE as the highest-priority source.
2. If `questionnaire_answers` contains a matching question, use that answer EXACTLY.
3. Never invent completely fake skills, degrees, certifications, employers, dates, achievements, locations, salaries, work authorization status, or experience.
4. If information is unavailable, try to guess or infer the answer based on context, skills, and projects in the given user info and resume. If it is impossible to infer, return:

   * "Not specified" for text fields.
   * "" for optional fields.
   * A valid available option only for select/radio fields.
5. For experience questions:

   * Calculate from resume evidence.
   * Return digits only ("2", "3").
   * If no evidence exists, return "0".
6. Select/Radio answers MUST exactly match one available option from HTML.
7. Preserve existing values:

   * If input has a `value` attribute, keep it.
   * If checkbox/radio is already `checked`, keep it.
8. Numeric fields:

   * Digits only.
   * No units, symbols, or text.
9. Checkbox fields:

   * Required consent/agreement → "true".
   * Otherwise preserve existing state when present.
10. Text/Textarea:

* Professional and concise.
* Maximum 2 sentences.

11. Work Authorization:

* Use profile/resume evidence only.
* If unavailable, choose the safest matching option from HTML.

12. Visa Sponsorship:

* Use profile/resume evidence only.
* Do not assume.

13. Never generate values not present in or reasonably inferred from resume/profile/HTML.
14. Every returned answer must include:

* `qa_idx`
* `label`
* `type`
* `answer`
* `selector`

15. Output ONLY valid JSON. No markdown, explanations, comments, or extra text.

### VALIDATION CHECK

Before returning:

* Ensure every `answer` is supported by or reasonably inferred from resume, profile, HTML, or existing field values.
* Verify all select/radio values exactly match available HTML options.
* Return a single JSON object with the key "answers" only.
"""
