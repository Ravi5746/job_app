from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

class WorkExperienceBase(BaseModel):
    company: str
    job_title: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    original_end_date_str: Optional[str] = None
    skills: Optional[List[str]] = None
    summary: Optional[str] = None

class WorkExperienceCreate(WorkExperienceBase):
    pass

class WorkExperienceUpdate(WorkExperienceBase):
    company: Optional[str] = None
    job_title: Optional[str] = None

class WorkExperienceInDB(WorkExperienceBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class WorkExperience(WorkExperienceInDB):
    pass
