import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base_class import Base

# Use in-memory SQLite for testing models
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_create_extraction_run_and_fields():
    from app.models.extraction import ExtractionRun, ExtractedField, FieldStats
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        
        # 1. Create a run
        run = ExtractionRun(
            job_url="https://jobs.lever.co/example/123",
            company="Example Company",
            source="Lever",
            ats_type="lever",
            status="completed",
            total_steps=1,
            total_fields=2
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        assert run.id is not None
        assert run.status == "completed"

        # 2. Create a field linked to the run
        field = ExtractedField(
            run_id=run.id,
            step_number=1,
            label="First Name",
            field_type="text",
            required=True,
            canonical_name="first_name"
        )
        db.add(field)
        db.commit()
        db.refresh(field)
        assert field.id is not None
        assert field.run_id == run.id

        # 3. Create field stats
        stats = FieldStats(
            canonical_name="first_name",
            field_type="text",
            required=True,
            ats_type="lever",
            company="Example Company",
            total_count=1
        )
        db.add(stats)
        db.commit()
        db.refresh(stats)
        assert stats.id is not None
        assert stats.total_count == 1
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
