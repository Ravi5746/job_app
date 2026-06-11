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

    # Demographic / EEO
    gender = Column(String, nullable=True)               # "Male", "Female", "Non-binary", "Decline"
    disability_status = Column(String, nullable=True)    # "Yes", "No", "Decline"

    # Employment status
    currently_working_status = Column(Boolean, nullable=True)

    # Job preferences (user-editable + auto-populated from questionnaire)

    desired_job_titles = Column(JSON, nullable=True)     # ["Full Stack Developer", "Backend Engineer"]
    expected_salary = Column(String, nullable=True)      # "12-15 LPA" or "80000"
    notice_period = Column(String, nullable=True)        # "30 days", "Immediate"
    work_authorization = Column(String, nullable=True)   # "Authorized to work"
    requires_sponsorship = Column(Boolean, nullable=True)
    country_of_citizenship = Column(String, nullable=True)
    willing_to_relocate = Column(Boolean, nullable=True)
    languages = Column(JSON, nullable=True)              # ["English", "Hindi"]
    portfolio_url = Column(String, nullable=True)
    preferred_work_models = Column(JSON, nullable=True)  # ["Remote", "Hybrid", "On-site"]

    # Detailed Address
    address_line_1 = Column(String, nullable=True)
    address_line_2 = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state_province = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    country = Column(String, nullable=True)

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

    from sqlalchemy.orm import relationship
    work_experiences = relationship("WorkExperience", back_populates="user", cascade="all, delete-orphan")
