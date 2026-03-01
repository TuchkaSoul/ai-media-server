from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class DetectionTypeEnum(str, enum.Enum):
    object = "object"
    action = "action"
    face = "face"
    anomaly = "anomaly"


class AlertSeverityEnum(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertStatusEnum(str, enum.Enum):
    new = "new"
    acknowledged = "acknowledged"
    resolved = "resolved"


class AnalysisStatusEnum(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class UserRoleEnum(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class VideoStatusEnum(str, enum.Enum):
    recording = "recording"
    processed = "processed"
    archived = "archived"
    failed = "failed"


class SegmentTypeEnum(str, enum.Enum):
    keyframe = "keyframe"
    event = "event"
    important = "important"
    normal = "normal"


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(500))
    owner: Mapped[Optional[str]] = mapped_column(String(255))
    stream_url: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[Optional[str]] = mapped_column(String(50), default="720p")
    fps: Mapped[Optional[int]] = mapped_column(Integer, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    videos: Mapped[List["Video"]] = relationship(back_populates="camera", cascade="all, delete-orphan")


class MLModel(Base):
    __tablename__ = "models"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_models_name_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)

    analysis_runs: Mapped[List["AnalysisRun"]] = relationship(back_populates="model")


class StorageProfile(Base):
    __tablename__ = "storage_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    codec: Mapped[str] = mapped_column(String(50), nullable=False)
    bitrate_kbps: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution: Mapped[Optional[str]] = mapped_column(String(50))
    fps: Mapped[Optional[int]] = mapped_column(Integer)
    retention_days: Mapped[Optional[int]] = mapped_column(Integer)
    archive_after_days: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    videos: Mapped[List["Video"]] = relationship(back_populates="storage_profile")


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        Index("idx_videos_camera", "camera_id"),
        Index("idx_videos_profile", "model_profile_id"),
        Index("idx_videos_start_time", "start_time"),
        {"postgresql_partition_by": "RANGE (start_time)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("storage_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime, primary_key=True, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_mb: Mapped[Optional[Decimal]] = mapped_column(Numeric(100, 2))
    status: Mapped[VideoStatusEnum] = mapped_column(
        Enum(VideoStatusEnum, name="video_status_enum"),
        default=VideoStatusEnum.recording,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    duration_sec: Mapped[Optional[int]] = mapped_column(
        Integer,
        Computed("EXTRACT(EPOCH FROM (end_time - start_time))::INTEGER", persisted=True),
    )

    camera: Mapped["Camera"] = relationship(back_populates="videos")
    storage_profile: Mapped[Optional["StorageProfile"]] = relationship(back_populates="videos")
    segments: Mapped[List["VideoSegment"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    analysis_runs: Mapped[List["AnalysisRun"]] = relationship(back_populates="video", cascade="all, delete-orphan")


class VideoSegment(Base):
    __tablename__ = "video_segments"
    __table_args__ = (
        CheckConstraint("end_sec > start_sec", name="valid_segment_time"),
        ForeignKeyConstraint(
            ["video_id", "video_start_time"],
            ["videos.id", "videos.start_time"],
            ondelete="CASCADE",
            name="fk_segments_video",
        ),
        Index("idx_segments_video", "video_id", "video_start_time"),
        Index("idx_segments_type", "segment_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    video_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    start_sec: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    end_sec: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    segment_type: Mapped[SegmentTypeEnum] = mapped_column(
        Enum(SegmentTypeEnum, name="segment_type_enum"),
        default=SegmentTypeEnum.normal,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    video: Mapped["Video"] = relationship(
        back_populates="segments",
        primaryjoin="and_(VideoSegment.video_id == Video.id, VideoSegment.video_start_time == Video.start_time)",
        foreign_keys="[VideoSegment.video_id, VideoSegment.video_start_time]",
    )
    detections: Mapped[List["Detection"]] = relationship(back_populates="segment")


class Detection(Base):
    __tablename__ = "detections"
    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="chk_detections_confidence"),
        CheckConstraint("bbox_x BETWEEN 0 AND 1", name="chk_detections_bbox_x"),
        CheckConstraint("bbox_y BETWEEN 0 AND 1", name="chk_detections_bbox_y"),
        CheckConstraint("bbox_width BETWEEN 0 AND 1", name="chk_detections_bbox_width"),
        CheckConstraint("bbox_height BETWEEN 0 AND 1", name="chk_detections_bbox_height"),
        Index("idx_detections_video", "video_id"),
        Index("idx_detections_event_time", "event_time"),
        Index("idx_detections_track", "track_id"),
        Index("idx_detections_type", "detection_type"),
        {"postgresql_partition_by": "RANGE (event_time)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    segment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("video_segments.id", ondelete="SET NULL"),
        nullable=True,
    )
    detection_type: Mapped[DetectionTypeEnum] = mapped_column(
        Enum(DetectionTypeEnum, name="detection_type_enum"), nullable=False
    )
    object_class: Mapped[Optional[str]] = mapped_column(String(255))
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3))
    bbox_x: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    bbox_y: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    bbox_width: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    bbox_height: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    event_time: Mapped[datetime] = mapped_column(DateTime, primary_key=True, nullable=False)
    track_id: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    segment: Mapped[Optional["VideoSegment"]] = relationship(back_populates="detections")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("idx_alerts_video", "video_id"),
        Index("idx_alerts_detection", "detection_id"),
        Index("idx_alerts_status", "status"),
        Index("idx_alerts_severity", "severity"),
        Index("idx_alerts_created_at", "created_at"),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    detection_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[AlertSeverityEnum] = mapped_column(
        Enum(AlertSeverityEnum, name="alert_severity_enum"),
        default=AlertSeverityEnum.medium,
        nullable=False,
    )
    status: Mapped[AlertStatusEnum] = mapped_column(
        Enum(AlertStatusEnum, name="alert_status_enum"),
        default=AlertStatusEnum.new,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, primary_key=True, server_default=func.now(), nullable=False)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["video_id", "video_start_time"],
            ["videos.id", "videos.start_time"],
            ondelete="CASCADE",
            name="fk_analysis_video",
        ),
        Index("idx_analysis_video", "video_id", "video_start_time"),
        Index("idx_analysis_model", "model_id"),
        Index("idx_analysis_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    video_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    model_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("models.id"))
    analysis_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[AnalysisStatusEnum] = mapped_column(
        Enum(AnalysisStatusEnum, name="analysis_status_enum"),
        default=AnalysisStatusEnum.pending,
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    parameters: Mapped[Optional[dict]] = mapped_column(JSONB)
    results_summary: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    video: Mapped["Video"] = relationship(
        back_populates="analysis_runs",
        primaryjoin="and_(AnalysisRun.video_id == Video.id, AnalysisRun.video_start_time == Video.start_time)",
        foreign_keys="[AnalysisRun.video_id, AnalysisRun.video_start_time]",
    )
    model: Mapped[Optional["MLModel"]] = relationship(back_populates="analysis_runs")


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "embedding_model", name="uq_embeddings_entity_model"),
        Index("idx_embeddings_entity", "entity_type", "entity_id"),
        Index("idx_embeddings_collection", "qdrant_collection"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    qdrant_collection: Mapped[str] = mapped_column(String(100), nullable=False)
    qdrant_point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    delete_pending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ProcessingError(Base):
    __tablename__ = "processing_errors"
    __table_args__ = (
        Index("idx_errors_entity", "entity_type", "entity_id"),
        Index("idx_errors_time", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    error_code: Mapped[Optional[str]] = mapped_column(String(100))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    trace_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

