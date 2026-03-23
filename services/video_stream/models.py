from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import numpy as np


class VideoSourceType(Enum):
    """Типы источников, которые умеет обрабатывать сервис."""

    USB_CAMERA = "usb_camera"
    WEB_CAMERA = "web_camera"
    IP_CAMERA_RTSP = "ip_camera_rtsp"
    VIDEO_FILE = "video_file"
    IP_CAMERA_HTTP = "ip_camera_http"
    IP_CAMERA_ONVIF = "ip_camera_onvif"
    MJPEG_STREAM = "mjpeg_stream"
    HLS_STREAM = "hls_stream"
    WEBCAM_API = "webcam_api"
    CUSTOM = "custom"


class ConnectionStatus(Enum):
    """Статус подключения к видеопотоку."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"


@dataclass(slots=True)
class VideoSourceConfig:
    """Нормализованная конфигурация одного видеопотока."""

    source_type: VideoSourceType
    source_uri: str
    source_id: str
    camera_id: Optional[int] = None
    rtsp_username: Optional[str] = None
    rtsp_password: Optional[str] = None
    rtsp_channel: int = 0
    http_auth: Optional[tuple[str, str]] = None
    frame_width: int = 1280
    frame_height: int = 720
    fps: int = 15
    buffer_size: int = 32
    reconnect_attempts: int = 5
    reconnect_delay: float = 2.0
    timeout_sec: float = 10.0
    use_gpu: bool = False
    codec: str = "h264"
    protocols: list[str] = field(default_factory=lambda: ["tcp"])
    additional_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type.value,
            "source_uri": self.source_uri,
            "source_id": self.source_id,
            "camera_id": self.camera_id,
            "rtsp_username": self.rtsp_username,
            "rtsp_password": self.rtsp_password,
            "rtsp_channel": self.rtsp_channel,
            "http_auth": self.http_auth,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "fps": self.fps,
            "buffer_size": self.buffer_size,
            "reconnect_attempts": self.reconnect_attempts,
            "reconnect_delay": self.reconnect_delay,
            "timeout_sec": self.timeout_sec,
            "use_gpu": self.use_gpu,
            "codec": self.codec,
            "protocols": list(self.protocols),
            "additional_params": dict(self.additional_params),
        }


@dataclass(slots=True)
class FrameData:
    """Единый формат кадра внутри сервиса."""

    frame: np.ndarray
    timestamp: float
    frame_number: int
    source_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessedFrame:
    """Результат предобработки без мутации исходного FrameData."""

    frame: np.ndarray
    timestamp: float
    camera_id: str
    motion_score: float
    anomaly_score: float
    scene_score: float
    is_event: bool
    metadata: dict[str, Any] = field(default_factory=dict)
    frame_number: int = 0

    @property
    def source_id(self) -> str:
        return self.camera_id
