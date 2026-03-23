from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Detection, Event, FrameMetadata, VideoSegment


class MediaQueryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_segments(self, *, camera_id: int | None = None, limit: int = 100) -> list[VideoSegment]:
        stmt = select(VideoSegment).order_by(VideoSegment.started_at.desc()).limit(limit)
        if camera_id is not None:
            stmt = stmt.where(VideoSegment.camera_id == camera_id)
        return list(self.db.scalars(stmt).all())

    def get_segment(self, segment_id: int) -> VideoSegment | None:
        return self.db.get(VideoSegment, segment_id)

    def list_frames(
        self,
        *,
        camera_id: int | None = None,
        segment_id: int | None = None,
        limit: int = 100,
    ) -> list[FrameMetadata]:
        stmt = select(FrameMetadata).order_by(FrameMetadata.captured_at.desc()).limit(limit)
        if camera_id is not None:
            stmt = stmt.where(FrameMetadata.camera_id == camera_id)
        if segment_id is not None:
            stmt = stmt.where(FrameMetadata.segment_id == segment_id)
        return list(self.db.scalars(stmt).all())

    def get_frame(self, frame_id: int) -> FrameMetadata | None:
        return self.db.get(FrameMetadata, frame_id)

    def list_detections(
        self,
        *,
        frame_id: int | None = None,
        camera_id: int | None = None,
        limit: int = 100,
    ) -> list[Detection]:
        stmt = select(Detection).join(FrameMetadata).order_by(Detection.created_at.desc()).limit(limit)
        if frame_id is not None:
            stmt = stmt.where(Detection.frame_id == frame_id)
        if camera_id is not None:
            stmt = stmt.where(FrameMetadata.camera_id == camera_id)
        return list(self.db.scalars(stmt).all())

    def list_events(
        self,
        *,
        camera_id: int | None = None,
        segment_id: int | None = None,
        limit: int = 100,
    ) -> list[Event]:
        stmt = select(Event).order_by(Event.created_at.desc()).limit(limit)
        if camera_id is not None:
            stmt = stmt.where(Event.camera_id == camera_id)
        if segment_id is not None:
            stmt = stmt.where(Event.segment_id == segment_id)
        return list(self.db.scalars(stmt).all())
