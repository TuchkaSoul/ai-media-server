from common.structured_logging import get_logger
from worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="worker.ping")
def ping() -> dict[str, str]:
    logger.info("Ping task executed", extra={"event": "worker_ping"})
    return {"status": "ok", "service": "worker"}
