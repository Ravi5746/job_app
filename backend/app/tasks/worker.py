from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "tasks",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
)

celery_app.conf.task_routes = {
    "backend.tasks.jobs.*": {"queue": "jobs"},
}

@celery_app.task(name="test_task")
def test_task(name: str):
    return f"Hello {name}, Celery is working!"

