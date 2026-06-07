from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text
from sqlalchemy.sql import func
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    # Profile fields merged from UserProfile
    phone = Column(String, nullable=True)
    phone_country_code = Column(String, nullable=True)
    location = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    github_url = Column(String, nullable=True)
    summary = Column(Text, nullable=True)

    # Skills & Experience (extracted from resume by AI)
    skills = Column(JSON, nullable=True)                # ["Python", "React", "Docker", ...]
    work_experience = Column(JSON, nullable=True)        # [{company, role, start, end, description}, ...]
    projects = Column(JSON, nullable=True)               # [{name, description, technologies}, ...]
    total_years_experience = Column(Integer, nullable=True)
    education = Column(JSON, nullable=True)              # [{degree, institution, year, field}, ...]
    certifications = Column(JSON, nullable=True)         # [{name, issuer, year}, ...]

    # Job preferences (user-editable + auto-populated from questionnaire)
    desired_job_titles = Column(JSON, nullable=True)     # ["Full Stack Developer", "Backend Engineer"]
    expected_salary = Column(String, nullable=True)      # "12-15 LPA" or "80000"
    notice_period = Column(String, nullable=True)        # "30 days", "Immediate"
    work_authorization = Column(String, nullable=True)   # "Authorized to work"
    willing_to_relocate = Column(Boolean, nullable=True)
    languages = Column(JSON, nullable=True)              # ["English", "Hindi"]
    portfolio_url = Column(String, nullable=True)

    questionnaire = Column(JSON, default=lambda: [
        "What is your current location?",
        "Are you willing to relocate?",
        "What is your notice period?",
        "What is your expected salary?",
        "What is your highest level of education?",
        "How many years of professional experience do you have?",
        "Why are you interested in this role?",
    ])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
