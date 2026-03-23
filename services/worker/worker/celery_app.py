import os

from celery import Celery
from celery.signals import setup_logging as celery_setup_logging

from common.structured_logging import setup_logging

logger = setup_logging("worker")

broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
backend_url = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

celery_app = Celery("mediahub_worker", broker=broker_url, backend=backend_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    imports=("worker.tasks",),
    worker_hijack_root_logger=False,
    worker_redirect_stdouts=False,
    broker_connection_retry_on_startup=True,
)


@celery_setup_logging.connect
def configure_celery_logging(*args, **kwargs) -> None:
    setup_logging("worker")


logger.info("Celery application configured", extra={"event": "worker_configured"})
