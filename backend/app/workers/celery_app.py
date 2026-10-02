from celery import Celery

from app.config import settings

celery_app = Celery(
    "smart_ats_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.parse_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.PARSE_TIMEOUT_SECONDS * 2,
    task_soft_time_limit=settings.PARSE_TIMEOUT_SECONDS,
    worker_prefetch_multiplier=1,
)
