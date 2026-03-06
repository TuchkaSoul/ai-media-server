from worker.celery_app import celery_app


@celery_app.task(name="worker.ping")
def ping() -> dict[str, str]:
    return {"status": "ok", "service": "worker"}
