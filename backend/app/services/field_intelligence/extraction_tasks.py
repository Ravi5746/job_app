import logging
from app.celery_app import celery_app
from app.services.field_intelligence.extractor_service import ExtractorService

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="app.services.field_intelligence.extraction_tasks.run_extraction")
async def run_extraction(self, run_id: int):
    logger.info(f"Starting background extraction task for run_id={run_id}")
    service = ExtractorService()
    await service.execute(run_id)
