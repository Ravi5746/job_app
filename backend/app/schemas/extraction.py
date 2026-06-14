from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ExtractionRunCreate(BaseModel):
    job_id: int

class ExtractedFieldResponse(BaseModel):
    id: int
    step_number: int
    label: Optional[str] = None
    field_type: str
    required: bool
    placeholder: Optional[str] = None
    options: Optional[List[str]] = None
    canonical_name: str

    class Config:
        from_attributes = True

class ExtractionRunResponse(BaseModel):
    id: int
    job_url: str
    company: Optional[str] = None
    ats_type: Optional[str] = None
    status: str
    total_steps: Optional[int] = 0
    total_fields: Optional[int] = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True
