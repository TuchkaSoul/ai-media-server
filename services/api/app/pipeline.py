from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from sqlalchemy import select

from app.db.models import Camera, Detection, Event, FrameMetadata, VideoSegment
from app.db.session import SessionLocal
from app.schemas import CameraRuntimeStatus, FrameAnalysisIngest

_CURRENT_FILE = Path(__file__).resolve()
REPO_ROOT = next(
    (parent for parent in [_CURRENT_FILE.parent, *_CURRENT_FILE.parents] if (parent / "services").exists()),
    _CURRENT_FILE.parents[2],
)
SERVICES_DIR = REPO_ROOT / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.append(str(SERVICES_DIR))

from video_stream.video_source_manager import MultiSourceManager, ProcessedFrame, VideoSourceConfig, VideoSourceFactory


@dataclass
class RuntimeState:
    camera_id: int
    source_id: str
    pipeline_status: str = "idle"
    active_segment_id: int | None = None
    last_frame_number: int | None = None
    last_frame_at: datetime | None = None
    frames_persisted: int = 0


class CameraPipelineService:
    def __init__(self) -> None:
        self.source_manager = MultiSourceManager()
        self.source_manager.register_frame_handler(self.handle_frame)
        self.storage_root = Path(os.getenv("STORAGE_PATH", str(REPO_ROOT / "storage" / "videos")))
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.auto_start = os.getenv("API_AUTO_START_CAMERAS", "false").lower() == "true"
        self.runtime: dict[int, RuntimeState] = {}
        self.source_to_camera: dict[str, int] = {}
        self.lock = RLock()

    def startup(self) -> None:
        if not self.auto_start:
            return

        with SessionLocal() as db:
            cameras = db.scalars(select(Camera).where(Camera.is_active.is_(True))).all()
            for camera in cameras:
                self.start_camera(camera.id, db=db)

    def shutdown(self) -> None:
        self.source_manager.stop_all()
        with self.lock:
            camera_ids = list(self.runtime.keys())
        for camera_id in camera_ids:
            self._close_active_segment(camera_id, reason="shutdown")

    def get_runtime_status(self, camera_id: int) -> CameraRuntimeStatus | None:
        with self.lock:
            state = self.runtime.get(camera_id)
            if state is None:
                return None
            info = self.source_manager.get_source_info(state.source_id)
            source_status = info["status"] if info else "missing"
            return CameraRuntimeStatus(
                camera_id=state.camera_id,
                source_id=state.source_id,
                pipeline_status=state.pipeline_status,
                source_status=source_status,
                active_segment_id=state.active_segment_id,
                last_frame_number=state.last_frame_number,
                last_frame_at=state.last_frame_at,
                frames_persisted=state.frames_persisted,
            )

    def list_runtime_statuses(self) -> list[CameraRuntimeStatus]:
        with self.lock:
            camera_ids = list(self.runtime.keys())
        return [status for camera_id in camera_ids if (status := self.get_runtime_status(camera_id)) is not None]

    def start_camera(self, camera_id: int, db=None) -> CameraRuntimeStatus:
        owns_session = db is None
        if owns_session:
            db = SessionLocal()

        try:
            camera = db.get(Camera, camera_id)
            if camera is None:
                raise ValueError(f"Camera {camera_id} not found")

            config = self._build_source_config(camera)
            if not self.source_manager.has_source(camera.source_id):
                added = self.source_manager.add_source(config)
                if not added:
                    raise ValueError(f"Source {camera.source_id} already exists or invalid")

            if not self.source_manager.start_source(camera.source_id):
                raise ValueError(f"Unable to start source {camera.source_id}")

            with self.lock:
                state = self.runtime.get(camera.id) or RuntimeState(camera_id=camera.id, source_id=camera.source_id)
                state.pipeline_status = "running"
                self.runtime[camera.id] = state
                self.source_to_camera[camera.source_id] = camera.id

            camera.status = "running"
            self._ensure_active_segment(camera, db)
            self._create_event(
                db,
                camera_id=camera.id,
                segment_id=self.runtime[camera.id].active_segment_id,
                event_type="camera_started",
                payload={"source_type": camera.source_type, "source_uri": camera.source_uri},
            )
            db.commit()
            db.refresh(camera)
            status = self.get_runtime_status(camera.id)
            if status is None:
                raise ValueError(f"Runtime state for camera {camera.id} is missing")
            return status
        except Exception:
            if owns_session:
                db.rollback()
            raise
        finally:
            if owns_session:
                db.close()

    def stop_camera(self, camera_id: int) -> CameraRuntimeStatus:
        with SessionLocal() as db:
            camera = db.get(Camera, camera_id)
            if camera is None:
                raise ValueError(f"Camera {camera_id} not found")

            self.source_manager.remove_source(camera.source_id)
            self._close_active_segment(camera_id, reason="stopped", db=db)

            with self.lock:
                state = self.runtime.get(camera_id) or RuntimeState(camera_id=camera_id, source_id=camera.source_id)
                state.pipeline_status = "stopped"
                self.runtime[camera_id] = state
                self.source_to_camera[camera.source_id] = camera_id

            camera.status = "stopped"
            self._create_event(db, camera_id=camera_id, event_type="camera_stopped", payload={"reason": "manual"})
            db.commit()
            status = self.get_runtime_status(camera_id)
            if status is None:
                raise ValueError(f"Runtime state for camera {camera_id} is missing")
            return status

    def ingest_analysis(self, frame_id: int, payload: FrameAnalysisIngest) -> FrameMetadata:
        with SessionLocal() as db:
            frame = db.get(FrameMetadata, frame_id)
            if frame is None:
                raise ValueError(f"Frame {frame_id} not found")

            for item in payload.detections:
                db.add(
                    Detection(
                        frame_id=frame.id,
                        label=item.label,
                        confidence=item.confidence,
                        track_id=item.track_id,
                        bbox=item.bbox,
                        attributes=item.attributes,
                    )
                )

            for item in payload.events:
                db.add(
                    Event(
                        camera_id=frame.camera_id,
                        segment_id=frame.segment_id,
                        frame_id=frame.id,
                        event_type=item.event_type,
                        importance_score=item.importance_score,
                        payload=item.payload,
                    )
                )

            frame.has_detections = frame.has_detections or bool(payload.detections)
            attributes = dict(frame.attributes)
            attributes["analysis_ingested_at"] = datetime.now(UTC).isoformat()
            attributes["analysis_detection_count"] = len(payload.detections)
            frame.attributes = attributes
            db.commit()
            db.refresh(frame)
            return frame

    def handle_frame(self, frame_data: ProcessedFrame) -> None:
        with self.lock:
            camera_id = self.source_to_camera.get(frame_data.source_id)
        if camera_id is None:
            return

        with SessionLocal() as db:
            camera = db.get(Camera, camera_id)
            if camera is None:
                return

            segment = self._ensure_active_segment(camera, db, frame_data.timestamp)
            captured_at = datetime.fromtimestamp(frame_data.timestamp, tz=UTC)
            frame = FrameMetadata(
                camera_id=camera.id,
                segment_id=segment.id,
                frame_number=frame_data.frame_number,
                captured_at=captured_at,
                width=int(frame_data.frame.shape[1]),
                height=int(frame_data.frame.shape[0]),
                ingest_latency_ms=round(max(0.0, (datetime.now(UTC) - captured_at).total_seconds() * 1000), 3),
                has_detections=bool(frame_data.metadata.get("detections")),
                attributes=self._build_frame_attributes(frame_data),
            )
            db.add(frame)
            segment.frame_count += 1
            camera.last_seen_at = captured_at
            camera.status = "running"
            db.flush()

            detections = frame_data.metadata.get("detections") or []
            for detection in detections:
                db.add(
                    Detection(
                        frame_id=frame.id,
                        label=str(detection.get("label") or detection.get("class_name") or "unknown"),
                        confidence=detection.get("confidence"),
                        track_id=detection.get("track_id"),
                        bbox=detection.get("bbox"),
                        attributes={
                            k: v
                            for k, v in detection.items()
                            if k not in {"label", "class_name", "confidence", "track_id", "bbox"}
                        },
                    )
                )

            if detections:
                self._create_event(
                    db,
                    camera_id=camera.id,
                    segment_id=segment.id,
                    frame_id=frame.id,
                    event_type="detections_received",
                    payload={"detection_count": len(detections)},
                )

            self._append_metadata_line(segment, frame)
            db.commit()

            with self.lock:
                state = self.runtime.get(camera.id) or RuntimeState(camera_id=camera.id, source_id=camera.source_id)
                state.pipeline_status = "running"
                state.active_segment_id = segment.id
                state.last_frame_number = frame.frame_number
                state.last_frame_at = frame.captured_at
                state.frames_persisted += 1
                self.runtime[camera.id] = state

    def _build_source_config(self, camera: Camera) -> VideoSourceConfig:
        payload = {
            "source_type": camera.source_type,
            "source_uri": camera.source_uri,
            "source_id": camera.source_id,
            "frame_width": camera.frame_width,
            "frame_height": camera.frame_height,
            "fps": camera.fps,
        }
        config = VideoSourceFactory.config_from_dict(payload)
        if config is None:
            raise ValueError(f"Unsupported source type: {camera.source_type}")
        return config

    def _ensure_active_segment(self, camera: Camera, db, frame_timestamp: float | None = None) -> VideoSegment:
        now = datetime.now(UTC) if frame_timestamp is None else datetime.fromtimestamp(frame_timestamp, tz=UTC)
        with self.lock:
            active_segment_id = self.runtime.get(camera.id).active_segment_id if camera.id in self.runtime else None

        segment = db.get(VideoSegment, active_segment_id) if active_segment_id else None
        if segment and segment.status == "open":
            age = (now - segment.started_at).total_seconds()
            if age < camera.segment_duration_seconds:
                return segment
            self._close_segment_record(db, segment, reason="rotation")
            self._create_event(
                db,
                camera_id=camera.id,
                segment_id=segment.id,
                event_type="segment_rotated",
                payload={"segment_index": segment.segment_index},
            )

        last_segment = db.scalar(
            select(VideoSegment)
            .where(VideoSegment.camera_id == camera.id)
            .order_by(VideoSegment.segment_index.desc())
            .limit(1)
        )
        segment_index = 1 if last_segment is None else last_segment.segment_index + 1
        storage_dir = self._segment_storage_dir(camera.id, now, segment_index)
        storage_dir.mkdir(parents=True, exist_ok=True)

        segment = VideoSegment(
            camera_id=camera.id,
            segment_index=segment_index,
            status="open",
            storage_path=str(storage_dir),
            metadata_path=str(storage_dir / "frames.jsonl"),
            started_at=now,
        )
        db.add(segment)
        db.flush()

        with self.lock:
            state = self.runtime.get(camera.id) or RuntimeState(camera_id=camera.id, source_id=camera.source_id)
            state.active_segment_id = segment.id
            self.runtime[camera.id] = state
            self.source_to_camera[camera.source_id] = camera.id

        return segment

    def _close_active_segment(self, camera_id: int, reason: str, db=None) -> None:
        owns_session = db is None
        if owns_session:
            db = SessionLocal()

        try:
            with self.lock:
                active_segment_id = self.runtime.get(camera_id).active_segment_id if camera_id in self.runtime else None

            if active_segment_id is None:
                if owns_session:
                    db.commit()
                return

            segment = db.get(VideoSegment, active_segment_id)
            if segment and segment.status == "open":
                self._close_segment_record(db, segment, reason)
                self._create_event(
                    db,
                    camera_id=camera_id,
                    segment_id=segment.id,
                    event_type="segment_closed",
                    payload={"reason": reason, "segment_index": segment.segment_index},
                )

            with self.lock:
                state = self.runtime.get(camera_id)
                if state is not None:
                    state.active_segment_id = None

            if owns_session:
                db.commit()
        finally:
            if owns_session:
                db.close()

    @staticmethod
    def _close_segment_record(db, segment: VideoSegment, reason: str) -> None:
        segment.status = "closed"
        segment.ended_at = datetime.now(UTC)
        manifest_path = Path(segment.storage_path) / "segment.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "segment_id": segment.id,
                    "segment_index": segment.segment_index,
                    "status": segment.status,
                    "reason": reason,
                    "frame_count": segment.frame_count,
                    "started_at": segment.started_at.isoformat(),
                    "ended_at": segment.ended_at.isoformat() if segment.ended_at else None,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        db.flush()

    def _append_metadata_line(self, segment: VideoSegment, frame: FrameMetadata) -> None:
        if not segment.metadata_path:
            return
        line = {
            "frame_id": frame.id,
            "frame_number": frame.frame_number,
            "captured_at": frame.captured_at.isoformat(),
            "width": frame.width,
            "height": frame.height,
            "has_detections": frame.has_detections,
            "attributes": frame.attributes,
        }
        metadata_path = Path(segment.metadata_path)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with metadata_path.open("a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(line, ensure_ascii=False) + "\n")

    @staticmethod
    def _build_frame_attributes(frame_data: ProcessedFrame) -> dict[str, Any]:
        metadata = dict(frame_data.metadata)
        metadata["source_id"] = frame_data.source_id
        metadata["shape"] = [int(value) for value in frame_data.frame.shape]
        return metadata

    def _segment_storage_dir(self, camera_id: int, current_time: datetime, segment_index: int) -> Path:
        return (
            self.storage_root
            / f"camera_{camera_id}"
            / current_time.strftime("%Y")
            / current_time.strftime("%m")
            / current_time.strftime("%d")
            / f"segment_{segment_index:06d}"
        )

    @staticmethod
    def _create_event(
        db,
        camera_id: int,
        event_type: str,
        payload: dict[str, Any],
        segment_id: int | None = None,
        frame_id: int | None = None,
    ) -> None:
        db.add(
            Event(
                camera_id=camera_id,
                segment_id=segment_id,
                frame_id=frame_id,
                event_type=event_type,
                payload=payload,
            )
        )
