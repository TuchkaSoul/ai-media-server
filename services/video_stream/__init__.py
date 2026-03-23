"""Публичный интерфейс пакета video_stream."""

from .camera_manager import CameraManager, VideoSourceFactory
from .consumer import DebugConsumer
from .models import ConnectionStatus, FrameData, ProcessedFrame, VideoSourceConfig, VideoSourceType
from .preprocessor import ScenePreprocessor, SceneScore
from .stream_reader import StreamReader

MultiSourceManager = CameraManager
VideoSource = StreamReader

__all__ = [
    "CameraManager",
    "ConnectionStatus",
    "DebugConsumer",
    "FrameData",
    "MultiSourceManager",
    "ProcessedFrame",
    "ScenePreprocessor",
    "SceneScore",
    "StreamReader",
    "VideoSource",
    "VideoSourceConfig",
    "VideoSourceFactory",
    "VideoSourceType",
]
