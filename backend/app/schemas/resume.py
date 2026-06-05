from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ResumeBase(BaseModel):
    name: str

class ResumeCreate(ResumeBase):
    pass

class ResumeTextCreate(BaseModel):
    name: str
    content: str

class Resume(ResumeBase):
    id: int
    user_id: int
    content: Optional[str] = None
    file_path: Optional[str] = None
    search_suggestions: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
