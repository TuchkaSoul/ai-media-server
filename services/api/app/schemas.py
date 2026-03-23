from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CameraCreate(BaseModel):
    name: str
    source_type: str = Field(description="usb_camera, web_camera, ip_camera_rtsp, ip_camera_http, mjpeg_stream, hls_stream")
    source_uri: str = ""
    source_id: str | None = None
    fps: int = 15
    frame_width: int = 1280
    frame_height: int = 720
    segment_duration_seconds: int = 300
    is_active: bool = True


class CameraUpdate(BaseModel):
    name: str | None = None
    source_type: str | None = None
    source_uri: str | None = None
    fps: int | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    segment_duration_seconds: int | None = None
    is_active: bool | None = None


class CameraRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: str
    source_uri: str
    source_id: str
    status: str
    fps: int
    frame_width: int
    frame_height: int
    segment_duration_seconds: int
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SegmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    segment_index: int
    status: str
    storage_path: str
    metadata_path: str | None
    started_at: datetime
    ended_at: datetime | None
    frame_count: int
    created_at: datetime


class FrameMetadataRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    segment_id: int
    frame_number: int
    captured_at: datetime
    width: int
    height: int
    ingest_latency_ms: Decimal | None
    has_detections: bool
    attributes: dict[str, Any]
    created_at: datetime


class DetectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    frame_id: int
    label: str
    confidence: Decimal | None
    track_id: str | None
    bbox: dict[str, Any] | None
    attributes: dict[str, Any]
    created_at: datetime


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    segment_id: int | None
    frame_id: int | None
    event_type: str
    importance_score: Decimal | None
    payload: dict[str, Any]
    created_at: datetime


class CameraRuntimeStatus(BaseModel):
    camera_id: int
    source_id: str
    pipeline_status: str
    source_status: str
    active_segment_id: int | None
    last_frame_number: int | None
    last_frame_at: datetime | None
    frames_persisted: int


class DetectionCreate(BaseModel):
    label: str
    confidence: Decimal | None = None
    track_id: str | None = None
    bbox: dict[str, Any] | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class EventCreate(BaseModel):
    event_type: str
    importance_score: Decimal | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class FrameAnalysisIngest(BaseModel):
    detections: list[DetectionCreate] = Field(default_factory=list)
    events: list[EventCreate] = Field(default_factory=list)
