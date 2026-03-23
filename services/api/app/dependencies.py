from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.pipeline import CameraPipelineService
from app.services.camera_service import CameraService
from app.services.media_service import MediaQueryService

pipeline_service = CameraPipelineService()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_pipeline_service() -> CameraPipelineService:
    return pipeline_service


def get_camera_service(
    db: Annotated[Session, Depends(get_db)],
    pipeline: Annotated[CameraPipelineService, Depends(get_pipeline_service)],
) -> CameraService:
    return CameraService(db=db, pipeline=pipeline)


def get_media_query_service(db: Annotated[Session, Depends(get_db)]) -> MediaQueryService:
    return MediaQueryService(db=db)
