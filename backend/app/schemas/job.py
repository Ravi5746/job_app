from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class JobBase(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = "active"
    category: Optional[str] = None
    skills: Optional[str] = None
    requirements: Optional[str] = None
    match_score: Optional[int] = None
    match_suggestions: Optional[str] = None
    tailored_resume: Optional[str] = None
    expires_at: Optional[datetime] = None


class JobCreate(JobBase):
    pass

class JobUpdate(JobBase):
    title: Optional[str] = None
    company: Optional[str] = None
    status: Optional[str] = None

class JobInDBBase(JobBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Job(JobInDBBase):
    pass
