import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.db.session import get_db

client = TestClient(app)

@pytest.fixture
def mock_db():
    db = MagicMock()
    
    mock_job = MagicMock()
    mock_job.id = 1
    mock_job.url = "https://jobs.lever.co/example/123"
    mock_job.company = "Example Company"
    
    mock_run = MagicMock()
    mock_run.id = 42
    mock_run.job_id = 1
    mock_run.job_url = "https://jobs.lever.co/example/123"
    mock_run.company = "Example Company"
    mock_run.ats_type = None
    mock_run.status = "pending"
    mock_run.total_steps = 0
    mock_run.total_fields = 0
    mock_run.started_at = None
    mock_run.finished_at = None
    
    def mock_query(model):
        query_mock = MagicMock()
        filter_mock = MagicMock()
        if model.__name__ == "Job":
            filter_mock.first.return_value = mock_job
        elif model.__name__ == "ExtractionRun":
            filter_mock.first.return_value = mock_run
        query_mock.filter.return_value = filter_mock
        return query_mock
        
    db.query.side_effect = mock_query
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock(side_effect=lambda r: setattr(r, "id", 42))
    
    yield db

def test_create_extraction_run_endpoint(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    
    with patch("app.services.field_intelligence.extraction_tasks.run_extraction.delay") as mock_delay:
        response = client.post("/api/v1/extraction/run", json={"job_id": 1})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 42
        assert data["company"] == "Example Company"
        mock_delay.assert_called_once_with(42)
        
    app.dependency_overrides.clear()

def test_create_extraction_run_direct_execution(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    
    with patch("app.services.field_intelligence.extractor_service.ExtractorService.execute") as mock_execute:
        response = client.post("/api/v1/extraction/run?background=false", json={"job_id": 1})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 42
        mock_execute.assert_called_once_with(42)
        
    app.dependency_overrides.clear()
