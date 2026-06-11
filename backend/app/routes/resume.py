from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import os
import shutil
from pypdf import PdfReader
import re

from app.db.session import get_db, SessionLocal
from app.routes.auth import get_current_user
from app.models.resume import Resume as ResumeModel
from app.models.user import User
from app.schemas.resume import Resume as ResumeSchema, ResumeTextCreate
from app.core.logger import logger
from app.core.config import settings
from app.ai.hermes import hermes_agent

router = APIRouter()

UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "resumes")

# Ensure the upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def scrape_jobs_for_new_resume(resume_id: int, user_id: int, db_session_factory):
    """
    Background task to automatically:
    1. Generate search suggestions from the uploaded resume.
    2. Scrape the latest 24h jobs for those suggestions.
    3. Save the jobs and compute their ATS match score immediately.
    """
    logger.info(f"Background: Starting auto-scraping for resume {resume_id}")
    db = db_session_factory()
    try:
        resume = db.query(ResumeModel).filter(ResumeModel.id == resume_id).first()
        if not resume:
            logger.warning(f"Resume {resume_id} not found for background scraping.")
            return

        import json
        suggestions = []
        if resume.search_suggestions:
            try:
                suggestions = json.loads(resume.search_suggestions)
            except:
                pass

        if not suggestions:
            # Generate suggestions using AI
            suggestions = await hermes_agent.get_search_suggestions(resume.content)
            resume.search_suggestions = json.dumps(suggestions)
            db.commit()

        if not suggestions:
            suggestions = ["Software Engineer", "Full Stack Developer"]

        logger.info(f"Auto-scraping jobs for suggestions: {suggestions[:3]}")

        from app.services.scraper_service import scraper_service
        from app.services.job_service import job_service
        from app.models.job import Job as JobModel
        from app.schemas.job import JobCreate
        from datetime import datetime, timezone

        for query in suggestions[:3]:  # Top 3 terms to avoid hitting RapidAPI limits
            try:
                external_jobs = scraper_service.search_jobs(query, location="India", date_posted="today")
            except Exception as e:
                logger.error(f"Error scraping for suggestion '{query}': {e}")
                external_jobs = []

            if not external_jobs:
                continue

            for ext_job in external_jobs:
                job_url = ext_job.get("job_apply_link", "")
                if not job_url:
                    continue

                # Parse expiration datetime
                expires_at_str = ext_job.get("job_offer_expiration_datetime_utc")
                expires_at = None
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    except:
                        pass

                # Skip if already expired
                if expires_at and expires_at < datetime.now(timezone.utc):
                    continue

                category_to_save = query.lower()

                full_desc = ext_job.get("job_description", "")
                highlights = ext_job.get("job_highlights", {})
                qualifications = highlights.get("Qualifications", [])
                reqs = "\n".join(qualifications) if qualifications else "Check job description."

                job_in = JobCreate(
                    title=ext_job.get("job_title", "Unknown Title"),
                    company=ext_job.get("employer_name", "Unknown Company"),
                    location=f"{ext_job.get('job_city', '') or ''} {ext_job.get('job_country', '') or ''}".strip(),
                    description=full_desc,
                    url=job_url,
                    source=ext_job.get("job_publisher", "JSearch"),
                    category=category_to_save,
                    expires_at=expires_at,
                    status="active"
                )

                # Check if job already exists
                existing_job = db.query(JobModel).filter(JobModel.url == job_url).first()
                if not existing_job:
                    db_job = job_service.create(db, obj_in=job_in)
                    db.commit()
                    db.refresh(db_job)

                    # Calculate ATS score, suggestions, skills, and requirements in one pass
                    try:
                        analysis = await hermes_agent.analyze_job(full_desc, resume.content)
                        db_job.match_score = analysis.get("match_score")
                        db_job.match_suggestions = "\n".join(analysis.get("suggestions", []))
                        db_job.skills = analysis.get("skills") or "Technical Skills"
                        db_job.requirements = analysis.get("requirements") or reqs or "Check job description."
                        db.commit()
                    except Exception as match_err:
                        logger.error(f"Error calculating match score for job {db_job.id}: {match_err}")
                else:
                    # Update existing job and calculate match details in one pass
                    for field, value in job_in.model_dump().items():
                        setattr(existing_job, field, value)
                    
                    try:
                        analysis = await hermes_agent.analyze_job(full_desc, resume.content)
                        existing_job.match_score = analysis.get("match_score")
                        existing_job.match_suggestions = "\n".join(analysis.get("suggestions", []))
                        existing_job.skills = analysis.get("skills") or existing_job.skills or "Technical Skills"
                        existing_job.requirements = analysis.get("requirements") or existing_job.requirements or reqs or "Check job description."
                    except Exception as match_err:
                        logger.error(f"Error updating match score for job {existing_job.id}: {match_err}")
                    
                    db.commit()
    except Exception as e:
        logger.error(f"Error in background resume-based scraping: {e}")
    finally:
        db.close()

async def enrich_profile_background(resume_id: int, user_id: int, text_content: str, db_session_factory):
    """
    Background task to extract profile data via LLM and upsert into the database.
    """
    logger.info(f"Background: Starting profile enrichment for user {user_id} and resume {resume_id}")
    db = db_session_factory()
    try:
        profile_data = await hermes_agent.extract_profile_data(text_content)
        if profile_data:
            email = profile_data.get("email")
            if email:
                email_regex = r"^[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}$"
                if not re.match(email_regex, email.strip()):
                    profile_data.pop("email", None)
                else:
                    profile_data["email"] = email.strip()

            phone = profile_data.get("phone")
            if phone:
                clean_phone = re.sub(r"[^\d+]", "", phone)
                phone_regex = r"^\+?\d{7,15}$"
                if not re.match(phone_regex, clean_phone):
                    profile_data.pop("phone", None)
                else:
                    profile_data["phone"] = clean_phone

            await hermes_agent.store_user_profile(db, user_id, profile_data)
            logger.info(f"Background: Enriched profile data stored for user {user_id}")
            
            # Auto-trigger job scraping after enrichment
            await scrape_jobs_for_new_resume(resume_id, user_id, db_session_factory)
    except Exception as e:
        logger.error(f"Background profile enrichment failed: {e}")
    finally:
        db.close()

@router.post("/public-upload")
async def public_upload_resume(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Public endpoint for HR/admins to upload candidate resumes."""
    logger.info("Received public resume upload request")
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported currently.")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit.")
    await file.seek(0)

    try:
        # Extract text synchronously to find email
        file_path_temp = os.path.join(UPLOAD_DIR, f"temp_{file.filename}")
        with open(file_path_temp, "wb") as buffer:
            buffer.write(contents)
            
        reader = PdfReader(file_path_temp)
        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text()
            
        # Regex to find email
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", text_content)
        if not email_match:
            os.remove(file_path_temp)
            raise HTTPException(status_code=400, detail="Could not extract email from resume to create candidate.")
            
        email = email_match.group(0).lower().strip()
        
        # Find or create user
        user = db.query(User).filter(User.email == email).first()
        if not user:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            hashed_password = pwd_context.hash("TemporaryPassword123!") # Dummy password for public candidates
            
            # Try to get a basic name from text
            first_line = next((line.strip() for line in text_content.splitlines() if line.strip()), "")
            name = first_line if len(first_line.split()) >= 2 else "Unknown Candidate"
            
            user = User(email=email, hashed_password=hashed_password, full_name=name)
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created new candidate user with ID {user.id}")
            
        # Move file to proper name
        file_filename = f"user_{user.id}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, file_filename)
        os.rename(file_path_temp, file_path)
        
        # Create Resume
        db_resume = ResumeModel(
            user_id=user.id,
            name=file.filename,
            content=text_content,
            file_path=file_path
        )
        db.add(db_resume)
        db.commit()
        db.refresh(db_resume)
        
        # Trigger background enrichment
        background_tasks.add_task(enrich_profile_background, db_resume.id, user.id, text_content, SessionLocal)
        
        return {"message": "Resume uploaded successfully. Profile enrichment started.", "resume_id": db_resume.id, "user_id": user.id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in public upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process resume: {str(e)}")

@router.post("/upload", response_model=ResumeSchema)
async def upload_resume(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"Received resume upload request from user {current_user.id}")
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported currently."
        )

    # File size check (10MB max)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit.")
    await file.seek(0)

    try:
        # 1. Save file locally
        file_filename = f"user_{current_user.id}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, file_filename)
        
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
        logger.info(f"Saved file {file.filename} to {file_path}")

        # 2. Extract text from PDF
        logger.info(f"Extracting text from {file.filename}")
        reader = PdfReader(file_path)
        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text()
        logger.info(f"Extracted {len(text_content)} characters from PDF")

        # 3. Save to database
        db_resume = ResumeModel(
            user_id=current_user.id,
            name=file.filename,
            content=text_content,
            file_path=file_path
        )
        db.add(db_resume)
        db.commit()
        db.refresh(db_resume)
        logger.info(f"Resume record created with ID {db_resume.id}")

        # 4. Trigger profile enrichment in background (which also triggers job scraping)
        background_tasks.add_task(enrich_profile_background, db_resume.id, current_user.id, text_content, SessionLocal)
        logger.info(f"Background enrichment queued for resume ID {db_resume.id}")

        return db_resume
    except Exception as e:
        logger.error(f"Error uploading resume: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process resume: {str(e)}"
        )

@router.get("/", response_model=list[ResumeSchema])
async def get_my_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"Fetching resumes for user {current_user.id}")
    return db.query(ResumeModel).filter(ResumeModel.user_id == current_user.id).all()

from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any

class UserProfileUpdate(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    phone_country_code: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    summary: Optional[str] = None
    # Enrichment fields
    skills: Optional[List[str]] = None
    work_experience: Optional[List[Dict[str, Any]]] = None
    work_experiences: Optional[List[Dict[str, Any]]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    total_years_experience: Optional[int] = None
    education: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    languages: Optional[List[str]] = None
    # Job preferences
    desired_job_titles: Optional[List[str]] = None
    expected_salary: Optional[str] = None
    notice_period: Optional[str] = None
    work_authorization: Optional[str] = None
    requires_sponsorship: Optional[bool] = None
    country_of_citizenship: Optional[str] = None
    willing_to_relocate: Optional[bool] = None
    preferred_work_models: Optional[List[str]] = None
    questionnaire: Optional[List[Dict[str, str]]] = None

    # EEO / Demographic
    gender: Optional[str] = None
    disability_status: Optional[str] = None

    # Detailed Address
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

    @field_validator("expected_salary")
    @classmethod
    def validate_expected_salary(cls, v):
        if v is not None and v != "":
            # Strip spaces and commas for formatting flexibility
            clean_val = v.replace(",", "").replace(" ", "").strip()
            if not clean_val.isdigit():
                raise ValueError("Expected salary must contain digits only (e.g. 400000)")
            val_int = int(clean_val)
            if val_int <= 0:
                raise ValueError("Expected salary must be a positive number")
            return clean_val
        return v


def _build_profile_response(user) -> dict:
    """Build a standardized profile response dict from a User model instance."""
    # Normalize questionnaire
    q_data = user.questionnaire or []
    normalized_q = []
    for item in q_data:
        if isinstance(item, str):
            normalized_q.append({"question": item, "answer": ""})
        elif isinstance(item, dict):
            normalized_q.append({
                "question": item.get("question", ""),
                "answer": item.get("answer", "")
            })

    profile = {
        "full_name": user.full_name or "",
        "email": user.email,
        "phone": user.phone or "",
        "phone_country_code": user.phone_country_code or "",
        "location": user.location or "",
        "linkedin_url": user.linkedin_url or "",
        "github_url": user.github_url or "",
        "portfolio_url": user.portfolio_url or "NaN",
        "summary": user.summary or "",
        # Enrichment data
        "skills": user.skills or [],
        # Use a single work-experience source (DB relationship) to avoid duplicate rendering
        "work_experience": [
            {
                "id": exp.id,
                "company": exp.company or "",
                "job_title": exp.job_title or "",
                "start_date": str(exp.start_date) if exp.start_date else "",
                "end_date": exp.original_end_date_str if exp.original_end_date_str else (str(exp.end_date) if exp.end_date else ""),
                "skills": exp.skills or [],
                "summary": exp.summary or "",
            } for exp in getattr(user, 'work_experiences', [])
        ],
        "work_experiences": [
            {
                "id": exp.id,
                "company": exp.company or "",
                "job_title": exp.job_title or "",
                "start_date": str(exp.start_date) if exp.start_date else "",
                "end_date": exp.original_end_date_str if exp.original_end_date_str else (str(exp.end_date) if exp.end_date else ""),
                "skills": exp.skills or [],
                "summary": exp.summary or "",
            } for exp in getattr(user, 'work_experiences', [])
        ],

        "projects": user.projects or [],
        "total_years_experience": user.total_years_experience or 0,
        "education": user.education or [],
        "certifications": user.certifications or [],
        "languages": user.languages or [],
        # Job preferences
        "desired_job_titles": user.desired_job_titles or [],
        "expected_salary": user.expected_salary or "",
        "notice_period": user.notice_period or "",
        "work_authorization": user.work_authorization or "",
        "requires_sponsorship": user.requires_sponsorship,
        "country_of_citizenship": user.country_of_citizenship or "",
        "willing_to_relocate": user.willing_to_relocate,
        "preferred_work_models": user.preferred_work_models or [],
        "questionnaire": normalized_q,
        
        # EEO
        "gender": user.gender or "",
        "disability_status": user.disability_status or "",
        
        # Address
        "address_line_1": user.address_line_1 or "",
        "address_line_2": user.address_line_2 or "",
        "city": user.city or "",
        "state_province": user.state_province or "",
        "postal_code": user.postal_code or "",
        "country": user.country or "",
    }

    # Calculate profile completeness
    check_fields = [
        bool(user.full_name), bool(user.phone), bool(user.phone_country_code), bool(user.location),
        bool(user.summary), bool(user.linkedin_url),
        bool(user.skills), bool(user.work_experience),
        bool(user.projects),
        bool(user.education), bool(user.expected_salary),
        bool(user.notice_period), bool(user.work_authorization),
    ]
    profile["completeness"] = int((sum(check_fields) / len(check_fields)) * 100)

    return profile

@router.get("/my-profile", response_model=dict)
async def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"Retrieving stored profile for user {current_user.id}")
    return _build_profile_response(current_user)

@router.put("/my-profile", response_model=dict)
async def update_my_profile(
    profile_in: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"Updating stored profile for user {current_user.id}")
    
    # Basic contact info
    current_user.full_name = profile_in.full_name
    current_user.email = profile_in.email
    current_user.phone = profile_in.phone
    current_user.phone_country_code = profile_in.phone_country_code
    current_user.location = profile_in.location
    current_user.linkedin_url = profile_in.linkedin_url
    current_user.github_url = profile_in.github_url
    current_user.portfolio_url = profile_in.portfolio_url
    current_user.summary = profile_in.summary
    
    # Enrichment fields
    if profile_in.skills is not None:
        current_user.skills = profile_in.skills
    # Avoid updating JSON work_experience separately; DB relationship is the canonical source.
    if profile_in.work_experience is not None:
        current_user.work_experience = []

    if profile_in.work_experiences is not None:
        from app.models.work_experience import WorkExperience
        from app.services.date_normalizer import DateNormalizer
        db.query(WorkExperience).filter(WorkExperience.user_id == current_user.id).delete()
        for exp in profile_in.work_experiences:
            start_date, _ = DateNormalizer.normalize_date(exp.get("start_date") or "", is_end=False)
            end_date, _ = DateNormalizer.normalize_date(exp.get("end_date") or "", is_end=True)
            new_exp = WorkExperience(
                user_id=current_user.id,
                company=exp.get("company", ""),
                job_title=exp.get("job_title", ""),
                start_date=start_date,
                end_date=end_date,
                original_end_date_str=exp.get("end_date") or "",
                skills=exp.get("skills") or [],
                summary=exp.get("summary", "")
            )
            db.add(new_exp)
    if profile_in.projects is not None:
        current_user.projects = profile_in.projects
    if profile_in.total_years_experience is not None:
        current_user.total_years_experience = profile_in.total_years_experience
    if profile_in.education is not None:
        current_user.education = profile_in.education
    if profile_in.certifications is not None:
        current_user.certifications = profile_in.certifications
    if profile_in.languages is not None:
        current_user.languages = profile_in.languages
    
    # Job preferences
    if profile_in.desired_job_titles is not None:
        current_user.desired_job_titles = profile_in.desired_job_titles
    if profile_in.expected_salary is not None:
        current_user.expected_salary = profile_in.expected_salary
    if profile_in.notice_period is not None:
        current_user.notice_period = profile_in.notice_period
    if profile_in.work_authorization is not None:
        current_user.work_authorization = profile_in.work_authorization
    if profile_in.requires_sponsorship is not None:
        current_user.requires_sponsorship = profile_in.requires_sponsorship
    if profile_in.country_of_citizenship is not None:
        current_user.country_of_citizenship = profile_in.country_of_citizenship
    if profile_in.willing_to_relocate is not None:
        current_user.willing_to_relocate = profile_in.willing_to_relocate
    if profile_in.preferred_work_models is not None:
        current_user.preferred_work_models = profile_in.preferred_work_models

    if profile_in.gender is not None:
        current_user.gender = profile_in.gender
    if profile_in.disability_status is not None:
        current_user.disability_status = profile_in.disability_status

    if profile_in.address_line_1 is not None:
        current_user.address_line_1 = profile_in.address_line_1
    if profile_in.address_line_2 is not None:
        current_user.address_line_2 = profile_in.address_line_2
    if profile_in.city is not None:
        current_user.city = profile_in.city
    if profile_in.state_province is not None:
        current_user.state_province = profile_in.state_province
    if profile_in.postal_code is not None:
        current_user.postal_code = profile_in.postal_code
    if profile_in.country is not None:
        current_user.country = profile_in.country
    
    if profile_in.questionnaire is not None:
        current_user.questionnaire = profile_in.questionnaire
        
    try:
        db.commit()
        db.refresh(current_user)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile in database")

    return _build_profile_response(current_user)

@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume = db.query(ResumeModel).filter(
        ResumeModel.id == resume_id,
        ResumeModel.user_id == current_user.id
    ).first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Delete file if exists
    if resume.file_path and os.path.exists(resume.file_path):
        os.remove(resume.file_path)

    db.delete(resume)
    db.commit()
    return {"message": "Resume deleted successfully"}

@router.get("/suggestions", response_model=List[dict])
async def get_resume_suggestions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resumes = db.query(ResumeModel).filter(ResumeModel.user_id == current_user.id).order_by(ResumeModel.created_at.desc()).all()
    if not resumes:
        return [{"resume_name": "Default", "suggestions": ["Software Engineer", "Frontend Developer", "Python Developer"]}]
    
    import json
    all_suggestions = []
    
    for resume in resumes:
        resume_suggestions = []
        if resume.search_suggestions:
            try:
                resume_suggestions = json.loads(resume.search_suggestions)
            except:
                pass
        
        if not resume_suggestions:
            # Generate and save if not present
            resume_suggestions = await hermes_agent.get_search_suggestions(resume.content)
            resume.search_suggestions = json.dumps(resume_suggestions)
            db.commit()
            
        all_suggestions.append({
            "resume_id": resume.id,
            "resume_name": resume.name,
            "suggestions": resume_suggestions
        })
    
    return all_suggestions

from pydantic import BaseModel

class RoleOptimizeRequest(BaseModel):
    resume_id: int
    target_role: str
    job_description: str = ""

@router.post("/optimize-preview")
async def optimize_resume_preview(
    request_data: RoleOptimizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume = db.query(ResumeModel).filter(
        ResumeModel.id == request_data.resume_id,
        ResumeModel.user_id == current_user.id
    ).first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="Base resume not found")
        
    result = await hermes_agent.generate_optimized_resume_for_role(
        target_role=request_data.target_role,
        resume_content=resume.content,
        job_description=request_data.job_description
    )
    return result

@router.post("/save-text", response_model=ResumeSchema)
async def save_text_resume(
    resume_in: ResumeTextCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        db_resume = ResumeModel(
            user_id=current_user.id,
            name=resume_in.name,
            content=resume_in.content,
            file_path=None
        )
        db.add(db_resume)
        db.commit()
        db.refresh(db_resume)

        # Trigger automatic background job scraping and matching for the new resume
        background_tasks.add_task(scrape_jobs_for_new_resume, db_resume.id, current_user.id, SessionLocal)

        return db_resume
    except Exception as e:
        logger.error(f"Error saving text resume: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save resume: {str(e)}"
        )

from fastapi.responses import FileResponse, Response

@router.get("/{resume_id}/download")
async def download_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume = db.query(ResumeModel).filter(
        ResumeModel.id == resume_id,
        ResumeModel.user_id == current_user.id
    ).first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    if resume.file_path and os.path.exists(resume.file_path):
        return FileResponse(
            path=resume.file_path,
            filename=resume.name,
            media_type="application/pdf"
        )
    
    # If text-only optimized resume, return the text content as a download
    return Response(
        content=resume.content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={resume.name.replace('.pdf', '')}.txt"}
    )
