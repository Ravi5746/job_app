from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.models.job import Job
from app.models.extraction import ExtractionRun, ExtractedField
from app.schemas.extraction import ExtractionRunCreate, ExtractionRunResponse, ExtractedFieldResponse
from app.services.field_intelligence.extraction_tasks import run_extraction
from app.services.field_intelligence.extractor_service import ExtractorService

router = APIRouter()

@router.post("/run", response_model=ExtractionRunResponse)
async def create_extraction_run(payload: ExtractionRunCreate, background: bool = True, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == payload.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    run = ExtractionRun(
        job_id=job.id,
        job_url=job.url,
        company=job.company,
        status="pending",
        total_steps=0,
        total_fields=0
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    if background:
        # Trigger background Celery task
        run_extraction.delay(run.id)
    else:
        # Execute directly (synchronously) inside the request-response thread
        await ExtractorService().execute(run.id)
        # Refresh from database to get updated status and metrics
        db.refresh(run)

    return run

@router.get("/run/{run_id}", response_model=ExtractionRunResponse)
def get_extraction_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(ExtractionRun).filter(ExtractionRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Extraction run not found")
    return run

@router.get("/run/{run_id}/fields", response_model=List[ExtractedFieldResponse])
def get_extracted_fields(run_id: int, db: Session = Depends(get_db)):
    fields = db.query(ExtractedField).filter(ExtractedField.run_id == run_id).all()
    return fields
