from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Camera
from app.pipeline import CameraPipelineService
from app.schemas import CameraCreate, CameraRuntimeStatus, CameraUpdate, FrameAnalysisIngest


class CameraService:
    def __init__(self, db: Session, pipeline: CameraPipelineService) -> None:
        self.db = db
        self.pipeline = pipeline

    def create_camera(self, payload: CameraCreate) -> Camera:
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
        self.db.add(camera)
        self.db.commit()
        self.db.refresh(camera)
        return camera

    def list_cameras(self, *, active_only: bool = False) -> list[Camera]:
        stmt = select(Camera).order_by(Camera.created_at.desc())
        if active_only:
            stmt = stmt.where(Camera.is_active.is_(True))
        return list(self.db.scalars(stmt).all())

    def get_camera(self, camera_id: int) -> Camera | None:
        return self.db.get(Camera, camera_id)

    def require_camera(self, camera_id: int) -> Camera:
        camera = self.get_camera(camera_id)
        if camera is None:
            raise ValueError(f"Camera {camera_id} not found")
        return camera

    def update_camera(self, camera_id: int, payload: CameraUpdate) -> Camera:
        camera = self.require_camera(camera_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(camera, field, value)
        self.db.commit()
        self.db.refresh(camera)
        return camera

    def start_camera(self, camera_id: int) -> CameraRuntimeStatus:
        return self.pipeline.start_camera(camera_id, db=self.db)

    def stop_camera(self, camera_id: int) -> CameraRuntimeStatus:
        return self.pipeline.stop_camera(camera_id)

    def get_runtime_status(self, camera_id: int) -> CameraRuntimeStatus | None:
        return self.pipeline.get_runtime_status(camera_id)

    def list_runtime_statuses(self) -> list[CameraRuntimeStatus]:
        return self.pipeline.list_runtime_statuses()

    def get_snapshot_bytes(self, camera_id: int, *, quality: int) -> bytes:
        import cv2

        camera = self.require_camera(camera_id)
        frame_data = self.pipeline.source_manager.get_frame(camera.source_id, timeout=1.0)
        if frame_data is None:
            raise ValueError(f"Frame for camera {camera_id} not available")

        success, encoded = cv2.imencode(".jpg", frame_data.frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not success:
            raise RuntimeError(f"Snapshot encoding failed for camera {camera_id}")
        return encoded.tobytes()

    def ingest_frame_analysis(self, frame_id: int, payload: FrameAnalysisIngest):
        return self.pipeline.ingest_analysis(frame_id, payload)
