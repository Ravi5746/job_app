from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: Optional[bool] = True

    # Profile fields
    phone: Optional[str] = None
    phone_country_code: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    summary: Optional[str] = None

    # Skills & Experience
    skills: Optional[List[str]] = None
    work_experience: Optional[List[Dict[str, Any]]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    total_years_experience: Optional[int] = None
    education: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None

    # Demographic / EEO
    gender: Optional[str] = None
    disability_status: Optional[str] = None

    # Employment status
    currently_working_status: Optional[bool] = None

    # Job preferences

    desired_job_titles: Optional[List[str]] = None
    expected_salary: Optional[str] = None
    notice_period: Optional[str] = None
    work_authorization: Optional[str] = None
    requires_sponsorship: Optional[bool] = None
    country_of_citizenship: Optional[str] = None
    willing_to_relocate: Optional[bool] = None
    languages: Optional[List[str]] = None
    portfolio_url: Optional[str] = None
    preferred_work_models: Optional[List[str]] = None

    # Detailed Address
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    
    questionnaire: Optional[Any] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(UserBase):
    password: Optional[str] = None

from .work_experience import WorkExperience as WorkExperienceSchema

class UserInDBBase(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class User(UserInDBBase):
    work_experiences: Optional[List[WorkExperienceSchema]] = None


class UserQuestionnaire(BaseModel):
    """
    Contains a list of standard interview questions for a user.
    Users can add additional custom questions to this list.
    """
    questions: List[str] = Field(default_factory=lambda: [
        "What is your current location?",
        "Are you willing to relocate?",
        "What is your notice period?",
        "What is your expected salary?",
        "What is your highest level of education?",
        "How many years of professional experience do you have?",
        "Why are you interested in this role?",
    ])
