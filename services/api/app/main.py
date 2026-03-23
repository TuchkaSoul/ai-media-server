from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.db import Base, engine
from app.dependencies import pipeline_service
from app.routes import api_router

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


@app.get("/docs", include_in_schema=False)
def docs_redirect() -> RedirectResponse:
    return RedirectResponse(url="/swagger")


@app.on_event("startup")
def startup() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS mediahub")
    Base.metadata.create_all(bind=engine)
    pipeline_service.startup()


@app.on_event("shutdown")
def shutdown() -> None:
    pipeline_service.shutdown()
