from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    password: str

class UserUpdate(UserBase):
    password: Optional[str] = None

class UserInDBBase(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class User(UserInDBBase):
    pass


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
