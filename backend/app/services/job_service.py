from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.job import Job
from app.schemas.job import JobCreate, JobUpdate

class JobService:
    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> List[Job]:
        return db.query(Job).offset(skip).limit(limit).all()

    def create(self, db: Session, obj_in: JobCreate) -> Job:
        db_obj = Job(
            title=obj_in.title,
            company=obj_in.company,
            location=obj_in.location,
            description=obj_in.description,
            url=obj_in.url,
            source=obj_in.source,
            status=obj_in.status
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, id: int) -> Optional[Job]:
        return db.query(Job).filter(Job.id == id).first()

job_service = JobService()
