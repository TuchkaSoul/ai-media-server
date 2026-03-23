"""Публичный интерфейс пакета video_stream."""

from .camera_manager import CameraManager, VideoSourceFactory
from .models import ConnectionStatus, FrameData, VideoSourceConfig, VideoSourceType
from .preprocessor import ScenePreprocessor, SceneScore
from .stream_reader import StreamReader

MultiSourceManager = CameraManager
VideoSource = StreamReader

__all__ = [
    "CameraManager",
    "ConnectionStatus",
    "FrameData",
    "MultiSourceManager",
    "ScenePreprocessor",
    "SceneScore",
    "StreamReader",
    "VideoSource",
    "VideoSourceConfig",
    "VideoSourceFactory",
    "VideoSourceType",
]
