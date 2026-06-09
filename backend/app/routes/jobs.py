from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
import asyncio
import logging
from app.db.session import get_db, SessionLocal

from app.models.job import Job as JobModel
from app.schemas.job import Job, JobCreate, JobUpdate

from app.services.job_service import job_service
from app.services.scraper_service import scraper_service
from app.ai.hermes import hermes_agent
from app.services.automation_service import automation_service
from app.models.resume import Resume as ResumeModel
from app.models.saved_job import SavedJob as SavedJobModel
from app.routes.auth import get_current_user, get_current_active_superuser
from app.models.user import User as UserModel
from app.celery_app import apply_to_job_task, AsyncResult, _tasks
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

async def enrich_job_data(
    job_id: int, 
    external_job_id: str, 
    user_id: int, 
    db_session_factory, 
    description: Optional[str] = None, 
    qualifications_list: Optional[List[str]] = None
):
    """Background task to fetch full details, extract skills, and perform AI matching"""
    db = db_session_factory()
    try:
        full_desc = description
        reqs = "\n".join(qualifications_list) if qualifications_list else ""

        # Fallback to fetching details if not provided
        if not full_desc:
            details = scraper_service.get_job_details(external_job_id)
            if details:
                full_desc = details.get("job_description", "")
                highlights = details.get("job_highlights", {})
                reqs = "\n".join(highlights.get("Qualifications", []))
            
        if full_desc:
            db_job = db.query(JobModel).filter(JobModel.id == job_id).first()
            if db_job:
                db_job.description = full_desc
                
                # Consolidated Details Extraction & Matching
                resume = db.query(ResumeModel).filter(ResumeModel.user_id == user_id).order_by(ResumeModel.created_at.desc()).first()
                if resume:
                    try:
                        analysis = await hermes_agent.analyze_job(full_desc, resume.content)
                        db_job.skills = analysis.get("skills") or "Technical Skills"
                        db_job.requirements = analysis.get("requirements") or reqs or "Check job description."
                        db_job.match_score = analysis.get("match_score")
                        db_job.match_suggestions = "\n".join(analysis.get("suggestions", []))
                    except Exception as enrich_err:
                        logger.error(f"Error in consolidated background enrichment for job {job_id}: {enrich_err}")
                        db_job.skills = "Technical Skills"
                        db_job.requirements = reqs or "Check job description."
                else:
                    # Fallback if no resume exists for user yet
                    try:
                        extraction = await hermes_agent.extract_job_details(full_desc)
                        db_job.skills = extraction.get("skills", "Technical Skills")
                        db_job.requirements = extraction.get("requirements", reqs or "Check job description.")
                    except Exception:
                        db_job.skills = "Technical Skills"
                        db_job.requirements = reqs or "Check job description."
                
                db.commit()
    except Exception as e:
        logger.error(f"Error in background enrichment for job {job_id}: {e}")
    finally:
        db.close()
 
def cleanup_expired_jobs(db: Session):
    """Deletes jobs from the DB where expires_at is past current time."""
    try:
        db.query(JobModel).filter(JobModel.expires_at < datetime.now(timezone.utc)).delete()
        db.commit()
    except Exception as e:
        logger.error(f"Error cleaning up expired jobs: {e}")
        db.rollback()


@router.get("/saved-jobs", response_model=List[Job])
def get_saved_jobs(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    saved_jobs = db.query(SavedJobModel).filter(SavedJobModel.user_id == current_user.id).all()
    job_ids = [sj.job_id for sj in saved_jobs]
    if not job_ids:
        return []
    
    jobs = db.query(JobModel).filter(JobModel.id.in_(job_ids)).order_by(JobModel.created_at.desc()).all()
    return jobs

@router.post("/{job_id}/save")
def save_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    existing_save = db.query(SavedJobModel).filter(
        SavedJobModel.user_id == current_user.id,
        SavedJobModel.job_id == job_id
    ).first()
    
    if existing_save:
        return {"status": "success", "message": "Job already saved"}
        
    saved_job = SavedJobModel(user_id=current_user.id, job_id=job_id)
    db.add(saved_job)
    db.commit()
    return {"status": "success", "message": "Job saved successfully"}

@router.delete("/{job_id}/save")
def unsave_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    saved_job = db.query(SavedJobModel).filter(
        SavedJobModel.user_id == current_user.id,
        SavedJobModel.job_id == job_id
    ).first()
    
    if not saved_job:
        raise HTTPException(status_code=404, detail="Saved job not found")
        
    db.delete(saved_job)
    db.commit()
    return {"status": "success", "message": "Job removed from saved list"}


@router.get("/db-search/", response_model=List[Job])
def db_search_jobs(
    query: str,
    location: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 30
):
    cleanup_expired_jobs(db)
    # Base query
    stmt = db.query(JobModel)
    
    # Filter by title or category (case-insensitive)
    if query:
        search_filter = f"%{query}%"
        stmt = stmt.filter(
            (JobModel.title.ilike(search_filter)) | 
            (JobModel.category.ilike(search_filter))
        )
    
    # Filter by location
    if location and location.lower() != "india":
        loc_filter = f"%{location}%"
        stmt = stmt.filter(JobModel.location.ilike(loc_filter))
        
    # Filter by status
    if status and status.lower() != "all":
        stmt = stmt.filter(JobModel.status.ilike(status))
        
    jobs = stmt.order_by(JobModel.created_at.desc()).offset(skip).limit(limit).all()
    return jobs

@router.get("/", response_model=List[Job])
def read_jobs(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 30,
    category: Optional[str] = None,
    status: Optional[str] = None
):
    cleanup_expired_jobs(db)
    # Base query
    query_stmt = db.query(JobModel)
    
    # Filter by category if provided
    if category and category.lower() != "all":
        query_stmt = query_stmt.filter(JobModel.category.ilike(category))
        
    # Filter by status if provided
    if status and status.lower() != "all":
        query_stmt = query_stmt.filter(JobModel.status.ilike(status))
    
    # Sort by created_at descending and paginate
    jobs = query_stmt.order_by(JobModel.created_at.desc()).offset(skip).limit(limit).all()
    return jobs

@router.patch("/{job_id}", response_model=Job)
def update_job(
    job_id: int,
    job_in: JobUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    db_job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    update_data = job_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_job, field, value)
        
    db.commit()
    db.refresh(db_job)
    return db_job

@router.delete("/clear-all")
def clear_all_jobs(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_superuser)
):
    try:
        db.query(JobModel).delete()
        db.commit()
        return {"status": "success", "message": "All jobs deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_superuser)
):
    db_job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(db_job)
    db.commit()
    return {"status": "success", "message": "Job deleted successfully"}

@router.get("/search/", response_model=List[Job])
async def search_external_jobs(
    query: str,
    location: str = "India",
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    # Try fetching from external API (JSearch)
    try:
        external_jobs = scraper_service.search_jobs(query, location)
    except Exception as e:
        logger.error(f"Scraper error: {e}")
        external_jobs = []

    mapped_jobs = []
    seen_urls = set()
    
    # Use lowercase query as the category for all new jobs to prevent case-sensitive duplicates
    category_to_save = query.lower() if query else "General"

    if external_jobs:
        for ext_job in external_jobs:
            job_url = ext_job.get("job_apply_link", "")
            if not job_url or job_url in seen_urls:
                continue
            
            seen_urls.add(job_url)

            # Parse expiration datetime
            expires_at_str = ext_job.get("job_offer_expiration_datetime_utc")
            expires_at = None
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                except Exception as e:
                    logger.error(f"Error parsing job expiration '{expires_at_str}': {e}")


            # Skip saving if already expired
            if expires_at and expires_at < datetime.now(timezone.utc):
                continue
            
            job_in = JobCreate(
                title=ext_job.get("job_title", "Unknown Title"),
                company=ext_job.get("employer_name", "Unknown Company"),
                location=f"{ext_job.get('job_city', '') or ''} {ext_job.get('job_country', '') or ''}".strip(),
                description=ext_job.get("job_description", ""),
                url=job_url,
                source=ext_job.get("job_publisher", "JSearch"),
                category=category_to_save,
                expires_at=expires_at,
                status="active"
            )
            
            existing_job = db.query(JobModel).filter(JobModel.url == job_url).first()
            
            full_desc = ext_job.get("job_description", "")
            highlights = ext_job.get("job_highlights", {})
            qualifications = highlights.get("Qualifications", [])

            if not existing_job:
                db_job = job_service.create(db, obj_in=job_in)
                mapped_jobs.append(db_job)
                ext_id = ext_job.get("job_id")
                if ext_id:
                    background_tasks.add_task(
                        enrich_job_data, 
                        db_job.id, 
                        ext_id, 
                        current_user.id, 
                        SessionLocal, 
                        full_desc, 
                        qualifications
                    )
            else:
                # Update existing job
                for field, value in job_in.model_dump().items():
                    setattr(existing_job, field, value)
                db.commit()
                mapped_jobs.append(existing_job)
                
                # Still queue match calculation if it hasn't been calculated yet
                ext_id = ext_job.get("job_id")
                if ext_id and not existing_job.match_score:
                    background_tasks.add_task(
                        enrich_job_data, 
                        existing_job.id, 
                        ext_id, 
                        current_user.id, 
                        SessionLocal, 
                        full_desc, 
                        qualifications
                    )
        
    return mapped_jobs



@router.post("/", response_model=Job)
def create_job(
    job_in: JobCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    return job_service.create(db, obj_in=job_in)

@router.get("/{job_id}", response_model=Job)
def read_job(job_id: int, db: Session = Depends(get_db)):
    db_job = job_service.get(db, id=job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    return db_job

@router.post("/optimize-resume/{job_id}")
async def optimize_job_resume(
    job_id: int,
    resume_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if resume_id:
        resume = db.query(ResumeModel).filter(ResumeModel.id == resume_id, ResumeModel.user_id == current_user.id).first()
    else:
        resume = db.query(ResumeModel).filter(ResumeModel.user_id == current_user.id).order_by(ResumeModel.created_at.desc()).first()
        
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found. Please upload one first.")
        
    # Just perform AI analysis and matching, skip tailoring
    analysis = await hermes_agent.analyze_job(job.description, resume.content)
    
    # Save results to DB
    import json
    # For UI compatibility, we store the original resume content in tailored_resume if requested to show a preview
    job.tailored_resume = json.dumps({
        "full_resume_text": resume.content,
        "ats_tips": analysis.get("suggestions", []),
        "match_score": analysis.get("match_score"),
        "match_suggestions": analysis.get("technical_alignment", "")
    })
    job.match_score = analysis.get("match_score")
    job.match_suggestions = "\n".join(analysis.get("suggestions", []))
    
    db.commit()
    
    return {
        "full_resume_text": resume.content,
        "ats_tips": analysis.get("suggestions", []),
        "match_score": analysis.get("match_score")
    }

@router.post("/apply/{job_id}")
async def apply_to_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # If match score is missing, calculate it briefly but don't tailor
    if not job.match_score:
        resume = db.query(ResumeModel).filter(ResumeModel.user_id == current_user.id).order_by(ResumeModel.created_at.desc()).first()
        if resume:
            analysis = await hermes_agent.analyze_job(job.description, resume.content)
            job.match_score = analysis.get("match_score")
            db.commit()

    logger.info(f"DEBUG: Enqueuing automation for job {job_id}")
    task = apply_to_job_task.delay(job_id, current_user.id)
    return {"status": "queued", "task_id": task.id}



@router.get("/apply/status/{task_id}")
def get_apply_status(task_id: str):
    res = AsyncResult(task_id)
    state = res.state
    
    result_data = None
    if state in ["COMPLETED", "SUCCESS", "FAILED", "FAILURE", "WARNING"]:
        info = res.info
        result_data = {"status": "success" if state in ["COMPLETED", "SUCCESS", "WARNING"] else "error", "message": info.get("message") if info else ""}
            
    return {
        "task_id": task_id,
        "status": state,
        "result": result_data
    }


@router.websocket("/apply/ws/{task_id}")
async def apply_ws_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()
    
    res = AsyncResult(task_id)
    initial_meta = res.info if isinstance(res.info, dict) else {"message": str(res.info)} if res.info else {}
    await websocket.send_json({
        "task_id": task_id,
        "status": res.state,
        "message": initial_meta.get("message", "Task is in progress...") if res.state not in ["SUCCESS", "COMPLETED"] else "Application completed."
    })
    
    last_message_count = 0
    try:
        while True:
            task = _tasks.get(task_id)
            if task:
                messages = task.get("messages", [])
                if len(messages) > last_message_count:
                    for i in range(last_message_count, len(messages)):
                        msg = messages[i]
                        await websocket.send_json({
                            "task_id": task_id,
                            "status": msg["status"],
                            "message": msg["message"]
                        })
                    last_message_count = len(messages)
            
            state = res.state
            if state in ["COMPLETED", "FAILED", "SUCCESS", "FAILURE", "WARNING"]:
                await websocket.send_json({
                    "task_id": task_id,
                    "status": state,
                    "message": "Task completed."
                })
                break
                
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for task {task_id}")
    except Exception as ws_err:
        logger.error(f"WebSocket error for task {task_id}: {ws_err}")

