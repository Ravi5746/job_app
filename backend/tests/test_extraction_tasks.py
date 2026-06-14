import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_celery_task_trigger():
    with patch("app.services.field_intelligence.extractor_service.ExtractorService.execute") as mock_execute:
        from app.services.field_intelligence.extraction_tasks import run_extraction
        # Call the underlying function of the CustomTask object
        await run_extraction.func(MagicMock(), 999)
        mock_execute.assert_called_once_with(999)
