from sqlalchemy.orm import Session
from app.models.job import Job

class JobController:
    def get_jobs(self, db: Session, skip: int = 0, limit: int = 100):
        return db.query(Job).offset(skip).limit(limit).all()

    def create_job(self, db: Session, job_data: dict):
        db_job = Job(**job_data)
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        return db_job

job_controller = JobController()

