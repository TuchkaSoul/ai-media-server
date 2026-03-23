from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CameraCreate(BaseModel):
    model_config = ConfigDict(
        title="CameraCreateRequest",
        json_schema_extra={
            "example": {
                "name": "Front Gate",
                "source_type": "ip_camera_rtsp",
                "source_uri": "rtsp://192.168.1.50:554/stream1",
                "source_id": "front_gate_cam",
                "fps": 15,
                "frame_width": 1280,
                "frame_height": 720,
                "segment_duration_seconds": 300,
                "is_active": True,
            }
        },
    )

    name: str = Field(description="Human-readable camera name.")
    source_type: str = Field(
        description="Source type: usb_camera, web_camera, ip_camera_rtsp, ip_camera_http, mjpeg_stream, hls_stream."
    )
    source_uri: str = Field(default="", description="Connection URI. Empty string is valid for local USB cameras.")
    source_id: str | None = Field(default=None, description="Stable internal source identifier. Generated automatically if omitted.")
    fps: int = Field(default=15, description="Target capture FPS.")
    frame_width: int = Field(default=1280, description="Requested frame width in pixels.")
    frame_height: int = Field(default=720, description="Requested frame height in pixels.")
    segment_duration_seconds: int = Field(default=300, description="Segment rotation duration in seconds.")
    is_active: bool = Field(default=True, description="Whether the camera is enabled for use.")


class CameraUpdate(BaseModel):
    model_config = ConfigDict(
        title="CameraUpdateRequest",
        json_schema_extra={
            "example": {
                "name": "Front Gate Main",
                "fps": 10,
                "segment_duration_seconds": 600,
                "is_active": True,
            }
        },
    )

    name: str | None = Field(default=None, description="Updated camera name.")
    source_type: str | None = Field(default=None, description="Updated source type.")
    source_uri: str | None = Field(default=None, description="Updated source URI.")
    fps: int | None = Field(default=None, description="Updated target FPS.")
    frame_width: int | None = Field(default=None, description="Updated frame width.")
    frame_height: int | None = Field(default=None, description="Updated frame height.")
    segment_duration_seconds: int | None = Field(default=None, description="Updated segment duration in seconds.")
    is_active: bool | None = Field(default=None, description="Updated active flag.")


class CameraRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        title="Camera",
    )

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
    model_config = ConfigDict(
        from_attributes=True,
        title="VideoSegment",
    )

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
    model_config = ConfigDict(
        from_attributes=True,
        title="FrameMetadata",
    )

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
    model_config = ConfigDict(
        from_attributes=True,
        title="Detection",
    )

    id: int
    frame_id: int
    label: str
    confidence: Decimal | None
    track_id: str | None
    bbox: dict[str, Any] | None
    attributes: dict[str, Any]
    created_at: datetime


class EventRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        title="Event",
    )

    id: int
    camera_id: int
    segment_id: int | None
    frame_id: int | None
    event_type: str
    importance_score: Decimal | None
    payload: dict[str, Any]
    created_at: datetime


class CameraRuntimeStatus(BaseModel):
    model_config = ConfigDict(title="CameraRuntimeStatus")

    camera_id: int = Field(description="Camera identifier.")
    source_id: str = Field(description="Underlying source identifier.")
    pipeline_status: str = Field(description="Pipeline state, for example running or stopped.")
    source_status: str = Field(description="Capture source state reported by the source manager.")
    active_segment_id: int | None = Field(description="Currently open segment identifier, if any.")
    last_frame_number: int | None = Field(description="Last persisted frame number.")
    last_frame_at: datetime | None = Field(description="Timestamp of the last persisted frame.")
    frames_persisted: int = Field(description="Total number of frames persisted in the current runtime session.")


class DetectionCreate(BaseModel):
    model_config = ConfigDict(title="DetectionCreate")

    label: str = Field(description="Detected class label.")
    confidence: Decimal | None = Field(default=None, description="Detection confidence score.")
    track_id: str | None = Field(default=None, description="Optional tracker identifier.")
    bbox: dict[str, Any] | None = Field(default=None, description="Bounding box payload.")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Additional detection metadata.")


class EventCreate(BaseModel):
    model_config = ConfigDict(title="EventCreate")

    event_type: str = Field(description="Domain event type.")
    importance_score: Decimal | None = Field(default=None, description="Optional event priority or score.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Additional event payload.")


class FrameAnalysisIngest(BaseModel):
    model_config = ConfigDict(
        title="FrameAnalysisIngestRequest",
        json_schema_extra={
            "example": {
                "detections": [
                    {
                        "label": "person",
                        "confidence": 0.9821,
                        "track_id": "trk-17",
                        "bbox": {"x1": 120, "y1": 80, "x2": 310, "y2": 540},
                        "attributes": {"direction": "in"},
                    }
                ],
                "events": [
                    {
                        "event_type": "person_detected",
                        "importance_score": 0.9,
                        "payload": {"zone": "entrance"},
                    }
                ],
            }
        },
    )

    detections: list[DetectionCreate] = Field(default_factory=list, description="Detections produced for the frame.")
    events: list[EventCreate] = Field(default_factory=list, description="Events produced for the frame.")
