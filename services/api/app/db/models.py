from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle", server_default="idle")
    fps: Mapped[int] = mapped_column(Integer, nullable=False, default=15, server_default="15")
    frame_width: Mapped[int] = mapped_column(Integer, nullable=False, default=1280, server_default="1280")
    frame_height: Mapped[int] = mapped_column(Integer, nullable=False, default=720, server_default="720")
    segment_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300, server_default="300")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    segments: Mapped[list["VideoSegment"]] = relationship(back_populates="camera", cascade="all, delete-orphan")
    frames: Mapped[list["FrameMetadata"]] = relationship(back_populates="camera", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="camera", cascade="all, delete-orphan")


class VideoSegment(Base):
    __tablename__ = "video_segments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    camera_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mediahub.cameras.id", ondelete="CASCADE"), nullable=False
    )
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", server_default="open")
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    frame_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    camera: Mapped["Camera"] = relationship(back_populates="segments")
    frames: Mapped[list["FrameMetadata"]] = relationship(back_populates="segment", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="segment")


class FrameMetadata(Base):
    __tablename__ = "frame_metadata"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    camera_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mediahub.cameras.id", ondelete="CASCADE"), nullable=False
    )
    segment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mediahub.video_segments.id", ondelete="CASCADE"), nullable=False
    )
    frame_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    ingest_latency_ms: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    has_detections: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    camera: Mapped["Camera"] = relationship(back_populates="frames")
    segment: Mapped["VideoSegment"] = relationship(back_populates="frames")
    detections: Mapped[list["Detection"]] = relationship(back_populates="frame", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="frame")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    frame_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mediahub.frame_metadata.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    track_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    frame: Mapped["FrameMetadata"] = relationship(back_populates="detections")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    camera_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mediahub.cameras.id", ondelete="CASCADE"), nullable=False
    )
    segment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mediahub.video_segments.id", ondelete="SET NULL"), nullable=True
    )
    frame_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mediahub.frame_metadata.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    importance_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    camera: Mapped["Camera"] = relationship(back_populates="events")
    segment: Mapped["VideoSegment | None"] = relationship(back_populates="events")
    frame: Mapped["FrameMetadata | None"] = relationship(back_populates="events")
