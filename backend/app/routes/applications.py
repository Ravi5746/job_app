from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any

from app.db.session import get_db
from app.models.application import Application, ApplicationStep
from app.models.job import Job
from app.routes.auth import get_current_user, get_current_active_superuser
from app.models.user import User

router = APIRouter()

@router.get("/")
def get_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
):
    """List all application records for the current user."""
    query = db.query(Application).filter(Application.user_id == current_user.id)
    apps = query.order_by(Application.applied_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for app in apps:
        job = db.query(Job).filter(Job.id == app.job_id).first()
        result.append({
            "id": app.id,
            "job_id": app.job_id,
            "job_title": job.title if job else "Unknown",
            "company": job.company if job else "Unknown",
            "status": app.status,
            "applied_at": app.applied_at,
            "notes": app.notes
        })
    return result

@router.get("/admin/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser)
):
    """Get aggregated statistics across all application runs (Admin/all users)."""
    total_apps = db.query(Application).count()
    if total_apps == 0:
        return {
            "total_applications": 0,
            "success_rate": 0.0,
            "average_duration_secs": 0.0,
            "total_tokens_input": 0,
            "total_tokens_output": 0,
            "total_cost": 0.0,
            "status_counts": {},
            "failure_reasons": []
        }

    applied_apps = db.query(Application).filter(Application.status == "applied").count()
    failed_apps = db.query(Application).filter(Application.status == "failed").count()
    success_rate = (applied_apps / total_apps) * 100.0 if total_apps > 0 else 0.0
    
    # Calculate stats from steps
    step_stats = db.query(
        func.sum(ApplicationStep.input_tokens).label("total_input"),
        func.sum(ApplicationStep.output_tokens).label("total_output"),
        func.sum(ApplicationStep.cost).label("total_cost")
    ).first()
    
    total_input = int(step_stats.total_input or 0)
    total_output = int(step_stats.total_output or 0)
    total_cost = float(step_stats.total_cost or 0.0)
    
    # Calculate average duration per application
    subquery = db.query(
        ApplicationStep.application_id,
        func.sum(ApplicationStep.duration_ms).label("total_duration")
    ).group_by(ApplicationStep.application_id).subquery()
    
    avg_duration_ms = db.query(func.avg(subquery.c.total_duration)).scalar()
    avg_duration_secs = float(avg_duration_ms / 1000.0) if avg_duration_ms else 0.0
    
    # Status breakdown
    status_counts = {}
    status_queries = db.query(Application.status, func.count(Application.id)).group_by(Application.status).all()
    for status, count in status_queries:
        status_counts[status] = count
        
    # Common failure reasons
    failures = db.query(Application.notes, func.count(Application.id)).filter(
        Application.status == "failed",
        Application.notes.isnot(None)
    ).group_by(Application.notes).order_by(func.count(Application.id).desc()).limit(5).all()
    
    failure_reasons = [{"reason": note, "count": count} for note, count in failures]
    
    return {
        "total_applications": total_apps,
        "success_rate": round(success_rate, 2),
        "average_duration_secs": round(avg_duration_secs, 2),
        "total_tokens_input": total_input,
        "total_tokens_output": total_output,
        "total_cost": round(total_cost, 6),
        "status_counts": status_counts,
        "failure_reasons": failure_reasons
    }
