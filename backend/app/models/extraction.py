from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON, UniqueConstraint
from sqlalchemy.sql import func
from app.db.session import Base

class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True, index=True)
    job_url = Column(String, nullable=False)
    company = Column(String, nullable=True, index=True)
    source = Column(String, nullable=True)
    ats_type = Column(String, nullable=True, index=True)
    status = Column(String, default="pending")  # pending, running, completed, failed_*
    error_message = Column(Text, nullable=True)
    total_steps = Column(Integer, default=0)
    total_fields = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("extraction_runs.id"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    label = Column(Text, nullable=True)
    field_type = Column(String, nullable=False)  # text, select, radio, checkbox, textarea, tel, email
    required = Column(Boolean, default=False)
    placeholder = Column(Text, nullable=True)
    options = Column(JSON, nullable=True)  # List of strings for dropdowns/options
    field_name = Column(String, nullable=True)
    field_id = Column(String, nullable=True)
    aria_label = Column(Text, nullable=True)
    canonical_name = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class FieldStats(Base):
    __tablename__ = "field_stats"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String, nullable=False, index=True)
    field_type = Column(String, nullable=True)
    required = Column(Boolean, default=False)
    ats_type = Column(String, nullable=True)
    company = Column(String, nullable=True)
    total_count = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint(
            "canonical_name", "field_type", "required", "ats_type", "company",
            name="uq_field_stats_dimensions"
        ),
    )
