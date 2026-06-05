import re
from typing import List, Dict
import json
from openai import AsyncOpenAI
from app.core.logger import logger
from app.core.config import settings
from sqlalchemy.orm import Session
from app.ai import prompts

class HermesAgent:
    """
    Hermes AI Agent for job matching and application optimization.
    Uses OpenRouter for semantic analysis."""
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.OPENAI_MODEL
        self.client = None
        
        # Determine if using Groq
        is_groq = self.model_name and ("llama-" in self.model_name or "groq" in self.model_name)
        
        if is_groq and settings.GROQ_API_KEY:
            self.client = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=settings.GROQ_API_KEY,
            )
            logger.info(f"HermesAgent initialized with Groq client using model: {self.model_name}")
        elif settings.OPENAI_API_KEY:
            self.client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.OPENAI_API_KEY,
            )
            logger.info(f"HermesAgent initialized with OpenRouter client using model: {self.model_name}")

    def _extract_keywords(self, text: str) -> set:
        if not text:
            return set()
        words = re.findall(r'\w+', text.lower())
        stop_words = {'a', 'the', 'is', 'in', 'at', 'of', 'and', 'to', 'for', 'with', 'on', 'our', 'we', 'you', 'your'}
        return {w for w in words if len(w) > 2 and w not in stop_words}
     
    def calculate_experience_years(self, work_experience: List[Dict]) -> int:
        """
        Robust total-experience calculator.
        Steps:
        1. Parse each role's start/end into date objects
        2. Sort intervals by start date
        3. Merge overlapping/adjacent intervals (prevents double-counting)
        4. Sum months from merged intervals (no +1 inflation)
        5. Floor-divide to years (conservative, industry-standard)
        """
        if not work_experience:
            return 0

        import datetime
        import re

        def parse_date(date_str: str, is_end: bool = False) -> datetime.date | None:
            if not date_str:
                return datetime.date.today() if is_end else None

            date_clean = date_str.strip().lower()

            if any(p in date_clean for p in ("present", "current", "now")):
                return datetime.date.today()

            MONTH_MAP = {
                "january": 1,  "february": 2,  "march": 3,    "april": 4,
                "may": 5,       "june": 6,      "july": 7,     "august": 8,
                "september": 9, "october": 10,  "november": 11,"december": 12,
                "jan": 1, "feb": 2, "mar": 3, "apr": 4,
                "jun": 6, "jul": 7, "aug": 8, "sep": 9,
                "oct": 10,"nov": 11,"dec": 12,
            }

            year_match = re.search(r"\b(19|20)\d{2}\b", date_str)
            if not year_match:
                return datetime.date.today() if is_end else None
            year = int(year_match.group(0))

            # Try named month (full names first to avoid "mar" matching "march" edge cases)
            month = None
            for m_name in sorted(MONTH_MAP, key=len, reverse=True):  # longest first
                if re.search(r"\b" + re.escape(m_name) + r"\b", date_clean):
                    month = MONTH_MAP[m_name]
                    break

            # Fallback: numeric month token (skip year digits)
            if month is None:
                year_str = year_match.group(0)
                for token in re.findall(r"\b(\d{1,2})\b", date_str):
                    if token not in (year_str, str(year)):
                        m_val = int(token)
                        if 1 <= m_val <= 12:
                            month = m_val
                            break

            # Last resort
            if month is None:
                month = 12 if is_end else 1

            return datetime.date(year, month, 1)

        # ── Step 1: Parse ──────────────────────────────────────────────────────────
        intervals: list[tuple[datetime.date, datetime.date]] = []
        for exp in work_experience:
            start = parse_date(exp.get("start"), is_end=False)
            end   = parse_date(exp.get("end"),   is_end=True)
            if not start or not end or start > end:
                continue
            intervals.append((start, end))

        if not intervals:
            return 0

        # ── Step 2 & 3: Sort, then merge overlapping/adjacent intervals ────────────
        intervals.sort(key=lambda x: x[0])
        merged: list[tuple[datetime.date, datetime.date]] = [intervals[0]]
        for start, end in intervals[1:]:
            prev_start, prev_end = merged[-1]
            if start <= prev_end:                        # overlap OR same-month join
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))

        # ── Step 4: Sum months from non-overlapping merged spans ──────────────────
        total_months = 0
        for start, end in merged:
            # No +1: (start=Feb, end=Feb same year) = 0, i.e. < 1 month worked
            months = (end.year - start.year) * 12 + (end.month - start.month)
            total_months += max(0, months)

        # ── Step 5: Convert — floor is conservative and industry-standard ─────────
        return max(0, total_months // 12)

        
    async def analyze_job(self, job_description: str, resume_content: str) -> Dict:
        """
        Analyzes the match between a job and a resume.
        Uses OpenRouter for semantic matching, falls back to keyword heuristic.
        """
        if not job_description or not resume_content:
            return {"match_score": 0, "suggestions": ["Provide both job description and resume for analysis."]}

        # Try semantic matching with OpenRouter
        if self.client:
            try:
                logger.info("Performing semantic matching with OpenRouter...")
                prompt = prompts.get_analyze_job_prompt(job_description, resume_content)
                
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    max_tokens=1000
                )
                
                if not response or not getattr(response, 'choices', None) or len(response.choices) == 0:
                    raise ValueError("No choices returned from OpenRouter.")
                raw_content = response.choices[0].message.content
                if not raw_content:
                    raise ValueError("Empty content returned from OpenRouter.")
                result = json.loads(raw_content)
                logger.info(f"AI Match Score: {result.get('match_score')}")
                return result

            except Exception as e:
                logger.error(f"OpenRouter matching failed: {str(e)}")
                # Fall back to keyword matching if AI fails

        # Fallback Heuristic matching
        logger.info("Falling back to keyword-based matching...")
        job_keywords = self._extract_keywords(job_description)
        resume_keywords = self._extract_keywords(resume_content)

        intersection = job_keywords.intersection(resume_keywords)
        score = int((len(intersection) / len(job_keywords)) * 100) if job_keywords else 0
        boosted_score = min(98, score + 20) if score > 0 else 0
        
        suggestions = [f"Focus on matching keywords like: {', '.join(list(job_keywords - resume_keywords)[:3])}"]
        if boosted_score < 70:
            suggestions.append("Your resume could be better optimized for this specific role.")
        
        return {
            "match_score": boosted_score,
            "suggestions": suggestions,
            "technical_alignment": "Keyword-based matching performed."
        }

    async def extract_job_details(self, job_description: str) -> Dict:
        """
        Uses AI to extract skills and requirements from a job description.
        """
        if not self.client or not job_description:
            # Fallback to simple extraction
            skills_list = re.findall(r'[A-Z][a-z]+(?:\.js|#|\+\+)?', job_description)
            return {
                "skills": ", ".join(list(set(skills_list))[:10]),
                "requirements": "See description for details."
            }

        try:
            prompt = prompts.get_extract_job_details_prompt(job_description)
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=500
            )
            if not response or not getattr(response, 'choices', None) or len(response.choices) == 0:
                raise ValueError("No choices returned from OpenRouter.")
            raw_content = response.choices[0].message.content
            if not raw_content:
                raise ValueError("Empty content returned from OpenRouter.")
            return json.loads(raw_content)
        except Exception:
            return self.extract_job_details("") # Trigger fallback

    async def calculate_match_score(self, job_description: str, resume_content: str) -> int:
        """
        Calculates a dynamic match score (0-100) between a job and a resume.
        """
        if not self.client or not resume_content:
            return 75 # Fallback

        try:
            prompt = prompts.get_calculate_match_score_prompt(job_description, resume_content)
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50
            )
            if not response or not getattr(response, 'choices', None) or len(response.choices) == 0:
                raise ValueError("No choices returned from OpenRouter.")
            raw_content = response.choices[0].message.content
            if not raw_content:
                raise ValueError("Empty content returned from OpenRouter.")
            score_text = raw_content.strip()
            # Extract only digits
            import re
            score = int(re.search(r'\d+', score_text).group())
            return min(100, max(0, score))
        except Exception:
            return 80 # Default if AI fails

    async def optimize_resume(self, job_description: str, resume_content: str) -> Dict:
        """
        Generates an optimized version of the resume sections for a specific job.
        """
        if not self.client:
            return {"optimized_content": "AI optimization unavailable without API key."}

        try:
            prompt = prompts.get_optimize_resume_prompt(job_description, resume_content)
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=4000
            )
            if not response or not getattr(response, 'choices', None) or len(response.choices) == 0:
                raise ValueError("No choices returned from OpenRouter.")
            raw_content = response.choices[0].message.content
            if not raw_content:
                raise ValueError("Empty content returned from OpenRouter.")
            data = json.loads(raw_content)
            return data
        except Exception as e:
            logger.error(f"Resume optimization failed: {str(e)}")
            return {"error": "Failed to optimize resume."}

    async def get_search_suggestions(self, resume_content: str) -> List[str]:
        """
        Suggests 5 job search queries based on the resume content.
        """
        if not self.client or not resume_content:
            return ["Software Engineer", "Full Stack Developer", "Backend Developer"]

        try:
            prompt = prompts.get_search_suggestions_prompt(resume_content)
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=300
            )
            if not response or not getattr(response, 'choices', None) or len(response.choices) == 0:
                raise ValueError("No choices returned from OpenRouter.")
            raw_content = response.choices[0].message.content
            if not raw_content:
                raise ValueError("Empty content returned from OpenRouter.")
            data = json.loads(raw_content)
            # Handle different JSON structures if AI returns an object
            if isinstance(data, dict):
                for val in data.values():
                    if isinstance(val, list): return val[:5]
            return data[:5] if isinstance(data, list) else ["Software Engineer"]
        except Exception:
            return ["Software Engineer", "Full Stack Developer", "Backend Developer"]

    async def generate_optimized_resume_for_role(self, target_role: str, resume_content: str, job_description: str = "") -> Dict:
        """
        Optimizes a resume specifically for a target industry role (e.g. "AI Engineer" or "Python Developer") and optional job description.
        Ensures strict architectural requirements: no section deletion, page density preservation,
        and updates professional keywords, projects, summaries, and competencies for modern industry requirements.
        """
        if not self.client:
            return {"optimized_content": "AI optimization unavailable without API key."}

        try:
            prompt = prompts.get_generate_optimized_resume_for_role_prompt(target_role, resume_content, job_description)
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=4000
            )
            if not response or not getattr(response, 'choices', None) or len(response.choices) == 0:
                raise ValueError("No choices returned from OpenRouter.")
            raw_content = response.choices[0].message.content
            if not raw_content:
                raise ValueError("Empty content returned from OpenRouter.")
            data = json.loads(raw_content)
            return data
        except Exception as e:
            logger.error(f"Role-based resume optimization failed: {str(e)}")
            return {"error": "Failed to optimize resume."}

    async def generate_cover_letter(self, job_details: dict, resume_details: dict):
        if self.client:
            try:
                prompt = prompts.get_generate_cover_letter_prompt(
                    job_details.get('title'),
                    job_details.get('company'),
                    resume_details.get('content')
                )
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1500
                )
                if not response or not getattr(response, 'choices', None) or len(response.choices) == 0:
                    raise ValueError("No choices returned from OpenRouter.")
                raw_content = response.choices[0].message.content
                if not raw_content:
                    raise ValueError("Empty content returned from OpenRouter.")
                return raw_content
            except Exception:
                pass
                
        return f"Dear Hiring Manager,\n\nI am writing to express my interest in the {job_details.get('title')} position..."

    async def extract_profile_data(self, resume_content: str) -> Dict:
        """
        Extracts structured profile data from a resume including:
        - Contact info (name, email, phone, location, URLs)
        - Skills list
        - Work experience with dates
        - Education details
        - Certifications
        - Languages
        - Total years of experience
        """
        if not resume_content:
            return {}

        # Compress resume text using local preprocessor pipeline
        try:
            from app.ai.compressor import ResumeCompressor
            resume_context = ResumeCompressor.compress_resume(resume_content)
            logger.info(f"Resume preprocessed and compressed from {len(resume_content)} to {len(resume_context)} chars.")
        except Exception as compress_err:
            logger.warning(f"Local compression failed ({compress_err}), falling back to raw truncation.")
            resume_context = resume_content[:15000]

        # Try AI extraction if client is available
        if self.client:
            try:
                prompt = prompts.get_extract_profile_data_prompt(resume_context)
                logger.info(f"[DEBUG] Sending prompt to OpenRouter model: {self.model_name} (Length: {len(prompt)})")
                try:
                    response = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                        max_tokens=4000
                    )
                except Exception as api_err:
                    if "llama-3.3" in self.model_name:
                        fallback_model = "llama-3.1-8b-instant"
                        logger.warning(f"Primary model {self.model_name} failed ({api_err}). Retrying with fallback model {fallback_model}...")
                        response = await self.client.chat.completions.create(
                            model=fallback_model,
                            messages=[{"role": "user", "content": prompt}],
                            response_format={"type": "json_object"},
                            max_tokens=2000
                        )
                    else:
                        raise api_err
                if not response or not getattr(response, 'choices', None) or len(response.choices) == 0:
                    raise ValueError("OpenRouter API returned an empty response or no choices.")
                
                choice = response.choices[0]
                if not getattr(choice, 'message', None):
                    raise ValueError("OpenRouter API response choice does not contain a message.")
                
                raw_content = choice.message.content
                if not raw_content:
                    reasoning = getattr(choice.message, 'reasoning', None)
                    if reasoning:
                        raise ValueError(f"OpenRouter model spent its tokens on reasoning instead of content: {reasoning[:200]}...")
                    raise ValueError("OpenRouter API returned empty content.")
                    
                logger.info(f"[DEBUG] AI Raw Response Length: {len(raw_content)} chars")
                logger.info(f"[DEBUG] AI Raw Response Content (last 200 chars): {raw_content[-200:]}")
                
                result = json.loads(raw_content)
                
                # Python-side validation to filter out projects from work_experience and move them to projects
                if "projects" not in result:
                    result["projects"] = []
                
                if "work_experience" in result and isinstance(result["work_experience"], list):
                    cleaned_work_exp = []
                    for exp in result["work_experience"]:
                        company = exp.get("company")
                        role = exp.get("role")
                        desc = exp.get("description") or ""
                        
                        # Identify if this entry is actually a project masquerading as a job
                        is_actually_project = False
                        if not company or company.lower().strip() in ("null", "none", "n/a", "self-employed", "freelance", "personal", "academic", "project", ""):
                            is_actually_project = True
                        elif role and any(keyword in role.lower() for keyword in ("project", "personal project", "academic project", "researchmind", "shopverse")):
                            is_actually_project = True
                        elif desc and any(keyword in desc.lower() for keyword in ("built a project", "personal project", "academic project")):
                            is_actually_project = True
                            
                        if is_actually_project:
                            proj_name = role or company or "Project"
                            # Make sure we don't add duplicates to the projects section
                            if not any(p.get("name", "").lower() == proj_name.lower() for p in result["projects"]):
                                result["projects"].append({
                                    "name": proj_name,
                                    "description": desc,
                                    "technologies": []
                                })
                            logger.info(f"Relocated project from work experience to projects: {proj_name}")
                        else:
                            cleaned_work_exp.append(exp)
                            
                    result["work_experience"] = cleaned_work_exp

                # Programmatically calculate and overwrite total years of experience using Python datetime
                if "work_experience" in result:
                    try:
                        calculated_years = self.calculate_experience_years(result["work_experience"])
                        logger.info(f"Programmatically calculated total years of experience: {calculated_years} (AI suggested: {result.get('total_years_experience')})")
                        result["total_years_experience"] = calculated_years
                    except Exception as calc_err:
                        logger.error(f"Error programmatically calculating experience years: {calc_err}")

                logger.info(f"AI extracted profile with {len(result.get('skills', []))} skills, "
                           f"{len(result.get('work_experience', []))} positions, "
                           f"{len(result.get('projects', []))} projects, "
                           f"{len(result.get('education', []))} education entries")
                return result
            except json.JSONDecodeError as jde:
                logger.error(f"[DEBUG] JSON Decode Error! Last 500 chars of raw response was: {raw_content[-500:] if 'raw_content' in locals() and raw_content else 'None'}")
                logger.error(f"[DEBUG] JSON Decode Exception: {jde}")
            except Exception as e:
                import traceback
                logger.error(f"[DEBUG] General Exception during AI extraction:")
                logger.error(traceback.format_exc())
                logger.error(f"Failed to extract profile data via AI (falling back to regex): {e}")


        # Fallback to simple regex extraction if AI client fails or is not configured
        logger.info("Using fallback regex profile extraction.")
        try:
            import re
            # Basic regex patterns for email and phone.
            email_match = re.search(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", resume_content)
            
            # Match phone numbers, optionally prefixed by label, allowing common separators
            phone_val = None
            phone_pattern = r"(?:phone|mobile|mob|tel|contact)?[:\s]*(\+?[\d\s()-.]{7,20})"
            phone_match = re.search(phone_pattern, resume_content, re.IGNORECASE)
            if phone_match:
                phone_val = phone_match.group(1).strip()
            else:
                phone_match = re.search(r"\+?[\d\s()-.]{10,20}", resume_content)
                if phone_match:
                    phone_val = phone_match.group(0).strip()

            # Attempt to get full name from the first non-empty line.
            first_line = next((line.strip() for line in resume_content.splitlines() if line.strip()), "")
            name_match = None
            if len(first_line.split()) >= 2 and all(word[0].isupper() for word in first_line.split() if word):
                name_match = first_line
            
            # Derive a simple summary
            summary_val = ""
            lines = resume_content.splitlines()
            for idx, line in enumerate(lines[:15]):
                if any(kw in line.upper() for kw in ["SUMMARY", "PROFILE", "OBJECTIVE"]):
                    summary_lines = []
                    for sub_line in lines[idx+1:idx+5]:
                        if sub_line.strip() and not any(h in sub_line.upper() for h in ["EXPERIENCE", "SKILLS", "EDUCATION"]):
                            summary_lines.append(sub_line.strip())
                    summary_val = " ".join(summary_lines)
                    break
            if not summary_val:
                summary_val = "Experienced professional."

            profile = {}
            if name_match:
                profile["full_name"] = name_match
            if email_match:
                profile["email"] = email_match.group(0)
            if phone_val:
                profile["phone"] = phone_val
            profile["summary"] = summary_val
            profile["skills"] = []
            profile["work_experience"] = []
            profile["projects"] = []
            profile["education"] = []
            profile["certifications"] = []
            profile["languages"] = []
            profile["total_years_experience"] = 0
            logger.info(f"Fallback profile extraction result: {profile}")
            return profile
        except Exception as fallback_err:
            logger.error(f"Fallback profile extraction failed: {fallback_err}")
            return {}

    async def store_user_profile(self, db: Session, user_id: int, profile_data: Dict) -> None:
        """
        Store or update the user's profile information extracted from the resume.
        Handles both basic contact info and enriched data (skills, experience, etc.).
        """
        try:
            from app.models.user import User
            
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"User {user_id} not found to store profile.")
                return

            # ── Basic contact info ──
            if "full_name" in profile_data and profile_data["full_name"]:
                user.full_name = profile_data["full_name"]
            if "phone" in profile_data:
                phone_val = profile_data["phone"]
                if phone_val:
                    import re
                    clean_phone = re.sub(r"[^\d+]", "", phone_val)
                    if re.match(r"^\+?\d{7,15}$", clean_phone):
                        user.phone = clean_phone
                    else:
                        user.phone = phone_val
                else:
                    user.phone = None
            if "current_location" in profile_data:
                user.location = profile_data["current_location"]
            elif "location" in profile_data:
                user.location = profile_data["location"]
            if "linkedin_url" in profile_data:
                user.linkedin_url = profile_data["linkedin_url"]
            if "github_url" in profile_data:
                user.github_url = profile_data["github_url"]
            if "portfolio_url" in profile_data:
                user.portfolio_url = profile_data["portfolio_url"]
            if "summary" in profile_data:
                user.summary = profile_data["summary"]

            # ── Skills & Experience (enrichment data) ──
            if "skills" in profile_data and isinstance(profile_data["skills"], list):
                user.skills = profile_data["skills"]
            if "work_experience" in profile_data and isinstance(profile_data["work_experience"], list):
                user.work_experience = profile_data["work_experience"]
            if "projects" in profile_data and isinstance(profile_data["projects"], list):
                user.projects = profile_data["projects"]
            if "total_years_experience" in profile_data:
                try:
                    user.total_years_experience = int(profile_data["total_years_experience"])
                except (ValueError, TypeError):
                    pass
            if "education" in profile_data and isinstance(profile_data["education"], list):
                user.education = profile_data["education"]
            if "certifications" in profile_data and isinstance(profile_data["certifications"], list):
                user.certifications = profile_data["certifications"]
            if "languages" in profile_data and isinstance(profile_data["languages"], list):
                user.languages = profile_data["languages"]

            db.commit()
            logger.info(f"Stored enriched profile for user {user_id}: "
                       f"{len(profile_data.get('skills', []))} skills, "
                       f"{len(profile_data.get('work_experience', []))} positions")
        except Exception as e:
            logger.error(f"Failed to store user profile: {e}")
            db.rollback()

hermes_agent = HermesAgent()
