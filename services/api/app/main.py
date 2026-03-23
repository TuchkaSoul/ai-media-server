import time

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from app.core.logging import bind_log_context, new_trace_id, reset_log_context, setup_logging
from app.db import Base, engine
from app.dependencies import pipeline_service
from app.routes import api_router

logger = setup_logging("api")

app = FastAPI(
    title="MediaHub API",
    version="0.2.0",
    description=(
        "Unified API for camera management, runtime control, frame ingestion, "
        "segments, detections, and events."
    ),
    openapi_tags=[
        {
            "name": "system",
            "description": "Service metadata and health checks.",
        },
        {
            "name": "cameras",
            "description": "Camera registry, runtime control, snapshots, and frame analysis ingestion.",
        },
        {
            "name": "media",
            "description": "Stored segments, frames, detections, and events.",
        },
    ],
    docs_url="/swagger",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.include_router(api_router)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Request-ID") or new_trace_id()
    token = bind_log_context(trace_id=trace_id)
    started_at = time.perf_counter()
    logger.info(
        "HTTP request received",
        extra={
            "event": "request_received",
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else None,
        },
    )
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "HTTP request failed",
            extra={
                "event": "request_failed",
                "method": request.method,
                "path": request.url.path,
                "latency_ms": duration_ms,
            },
        )
        reset_log_context(token)
        raise

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-ID"] = trace_id
    logger.info(
        "HTTP request completed",
        extra={
            "event": "request_completed",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": duration_ms,
        },
    )
    reset_log_context(token)
    return response


@app.get("/docs", include_in_schema=False)
def docs_redirect() -> RedirectResponse:
    return RedirectResponse(url="/swagger")


@app.on_event("startup")
def startup() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS mediahub")
    Base.metadata.create_all(bind=engine)
    pipeline_service.startup()
    logger.info("API service started", extra={"event": "service_started"})


@app.on_event("shutdown")
def shutdown() -> None:
    pipeline_service.shutdown()
    logger.info("API service stopped", extra={"event": "service_stopped"})
