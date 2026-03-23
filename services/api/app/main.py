from __future__ import annotations

from datetime import UTC, datetime

import cv2
from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import Base, Camera, Detection, Event, FrameMetadata, VideoSegment, engine, get_db
from app.pipeline import CameraPipelineService
from app.schemas import (
    CameraCreate,
    CameraRead,
    CameraRuntimeStatus,
    CameraUpdate,
    DetectionRead,
    EventRead,
    FrameAnalysisIngest,
    FrameMetadataRead,
    SegmentRead,
)

app = FastAPI(title="MediaHub API", version="0.2.0")
pipeline = CameraPipelineService()


@app.on_event("startup")
def startup() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS mediahub")
    Base.metadata.create_all(bind=engine)
    pipeline.startup()


@app.on_event("shutdown")
def shutdown() -> None:
    pipeline.shutdown()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "api",
        "status": "ok",
        "message": "MediaHub unified capture pipeline",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "healthy"}


@app.post("/cameras", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)) -> Camera:
    source_id = payload.source_id or f"camera_{payload.name.lower().replace(' ', '_')}"
    camera = Camera(
        name=payload.name,
        source_type=payload.source_type,
        source_uri=payload.source_uri,
        source_id=source_id,
        fps=payload.fps,
        frame_width=payload.frame_width,
        frame_height=payload.frame_height,
        segment_duration_seconds=payload.segment_duration_seconds,
        is_active=payload.is_active,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@app.get("/cameras", response_model=list[CameraRead])
def list_cameras(active_only: bool = Query(default=False), db: Session = Depends(get_db)) -> list[Camera]:
    stmt = select(Camera).order_by(Camera.created_at.desc())
    if active_only:
        stmt = stmt.where(Camera.is_active.is_(True))
    return list(db.scalars(stmt).all())


@app.get("/cameras/{camera_id}", response_model=CameraRead)
def get_camera(camera_id: int, db: Session = Depends(get_db)) -> Camera:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@app.patch("/cameras/{camera_id}", response_model=CameraRead)
def update_camera(camera_id: int, payload: CameraUpdate, db: Session = Depends(get_db)) -> Camera:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(camera, field, value)

    db.commit()
    db.refresh(camera)
    return camera


@app.post("/cameras/{camera_id}/start", response_model=CameraRuntimeStatus)
def start_camera(camera_id: int, db: Session = Depends(get_db)) -> CameraRuntimeStatus:
    try:
        return pipeline.start_camera(camera_id, db=db)
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc


@app.post("/cameras/{camera_id}/stop", response_model=CameraRuntimeStatus)
def stop_camera(camera_id: int) -> CameraRuntimeStatus:
    try:
        return pipeline.stop_camera(camera_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/cameras/{camera_id}/runtime", response_model=CameraRuntimeStatus)
def camera_runtime(camera_id: int) -> CameraRuntimeStatus:
    status_payload = pipeline.get_runtime_status(camera_id)
    if status_payload is None:
        raise HTTPException(status_code=404, detail="Runtime state not found")
    return status_payload


@app.get("/runtime/cameras", response_model=list[CameraRuntimeStatus])
def all_runtime_statuses() -> list[CameraRuntimeStatus]:
    return pipeline.list_runtime_statuses()


@app.get("/cameras/{camera_id}/snapshot")
def camera_snapshot(camera_id: int, quality: int = 85, db: Session = Depends(get_db)) -> Response:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    frame_data = pipeline.source_manager.get_frame(camera.source_id, timeout=1.0)
    if frame_data is None:
        raise HTTPException(status_code=404, detail="Frame not available")

    success, encoded = cv2.imencode(".jpg", frame_data.frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise HTTPException(status_code=500, detail="Snapshot encoding failed")
    return Response(content=encoded.tobytes(), media_type="image/jpeg")


@app.get("/segments", response_model=list[SegmentRead])
def list_segments(camera_id: int | None = None, limit: int = 100, db: Session = Depends(get_db)) -> list[VideoSegment]:
    stmt = select(VideoSegment).order_by(VideoSegment.started_at.desc()).limit(limit)
    if camera_id is not None:
        stmt = stmt.where(VideoSegment.camera_id == camera_id)
    return list(db.scalars(stmt).all())


@app.get("/segments/{segment_id}", response_model=SegmentRead)
def get_segment(segment_id: int, db: Session = Depends(get_db)) -> VideoSegment:
    segment = db.get(VideoSegment, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    return segment


@app.get("/frames", response_model=list[FrameMetadataRead])
def list_frames(
    camera_id: int | None = None,
    segment_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[FrameMetadata]:
    stmt = select(FrameMetadata).order_by(FrameMetadata.captured_at.desc()).limit(limit)
    if camera_id is not None:
        stmt = stmt.where(FrameMetadata.camera_id == camera_id)
    if segment_id is not None:
        stmt = stmt.where(FrameMetadata.segment_id == segment_id)
    return list(db.scalars(stmt).all())


@app.get("/frames/{frame_id}", response_model=FrameMetadataRead)
def get_frame(frame_id: int, db: Session = Depends(get_db)) -> FrameMetadata:
    frame = db.get(FrameMetadata, frame_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame metadata not found")
    return frame


@app.post("/frames/{frame_id}/analysis", response_model=FrameMetadataRead)
def ingest_frame_analysis(frame_id: int, payload: FrameAnalysisIngest) -> FrameMetadata:
    try:
        return pipeline.ingest_analysis(frame_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/detections", response_model=list[DetectionRead])
def list_detections(
    frame_id: int | None = None,
    camera_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[Detection]:
    stmt = select(Detection).join(FrameMetadata).order_by(Detection.created_at.desc()).limit(limit)
    if frame_id is not None:
        stmt = stmt.where(Detection.frame_id == frame_id)
    if camera_id is not None:
        stmt = stmt.where(FrameMetadata.camera_id == camera_id)
    return list(db.scalars(stmt).all())


@app.get("/events", response_model=list[EventRead])
def list_events(
    camera_id: int | None = None,
    segment_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[Event]:
    stmt = select(Event).order_by(Event.created_at.desc()).limit(limit)
    if camera_id is not None:
        stmt = stmt.where(Event.camera_id == camera_id)
    if segment_id is not None:
        stmt = stmt.where(Event.segment_id == segment_id)
    return list(db.scalars(stmt).all())
