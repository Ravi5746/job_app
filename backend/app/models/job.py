from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    company = Column(String, index=True, nullable=False)
    location = Column(String)
    description = Column(Text)
    url = Column(String)
    source = Column(String) # e.g., 'LinkedIn', 'Indeed'
    status = Column(String, default="active") # active, closed, etc.
    category = Column(String, index=True, nullable=True)
    skills = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)
    match_score = Column(Integer, nullable=True)
    match_suggestions = Column(Text, nullable=True)
    tailored_resume = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())



