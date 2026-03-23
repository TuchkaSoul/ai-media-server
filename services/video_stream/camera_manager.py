from __future__ import annotations

import threading
import time
from typing import Any, Callable, Protocol

import cv2

from common.structured_logging import get_logger
from .models import FrameData, VideoSourceConfig, VideoSourceType
from .preprocessor import ScenePreprocessor
from .stream_reader import StreamReader

logger = get_logger(__name__)


class FrameProcessor(Protocol):
    """Протокол для этапов обработки кадра внутри менеджера."""

    def process(self, frame_data: FrameData) -> FrameData:
        ...


class VideoSourceFactory:
    """Фабрика источников видео поверх текущего StreamReader."""

    SUPPORTED_SOURCE_TYPES = {
        VideoSourceType.USB_CAMERA,
        VideoSourceType.WEB_CAMERA,
        VideoSourceType.IP_CAMERA_RTSP,
        VideoSourceType.VIDEO_FILE,
        VideoSourceType.IP_CAMERA_HTTP,
        VideoSourceType.MJPEG_STREAM,
        VideoSourceType.HLS_STREAM,
        VideoSourceType.CUSTOM,
    }

    @staticmethod
    def create_source(config: VideoSourceConfig) -> StreamReader | None:
        if config.source_type not in VideoSourceFactory.SUPPORTED_SOURCE_TYPES:
            logger.error(
                "Тип источника пока не поддерживается",
                extra={"event": "unsupported_source_type", "source_type": config.source_type.value},
            )
            return None
        return StreamReader(config)

    @staticmethod
    def config_from_dict(config_dict: dict[str, Any]) -> VideoSourceConfig | None:
        try:
            source_type = VideoSourceType(config_dict["source_type"])
            return VideoSourceConfig(
                source_type=source_type,
                source_uri=str(config_dict.get("source_uri", "")),
                source_id=str(config_dict["source_id"]),
                camera_id=config_dict.get("camera_id"),
                rtsp_username=config_dict.get("rtsp_username"),
                rtsp_password=config_dict.get("rtsp_password"),
                rtsp_channel=int(config_dict.get("rtsp_channel", 0)),
                http_auth=config_dict.get("http_auth"),
                frame_width=int(config_dict.get("frame_width", 1280)),
                frame_height=int(config_dict.get("frame_height", 720)),
                fps=max(1, min(60, int(config_dict.get("fps", 15)))),
                buffer_size=max(1, int(config_dict.get("buffer_size", 32))),
                reconnect_attempts=max(1, int(config_dict.get("reconnect_attempts", 5))),
                reconnect_delay=float(config_dict.get("reconnect_delay", 2.0)),
                timeout_sec=float(config_dict.get("timeout_sec", 10.0)),
                use_gpu=bool(config_dict.get("use_gpu", False)),
                codec=str(config_dict.get("codec", "h264")),
                protocols=list(config_dict.get("protocols", ["tcp"])),
                additional_params=dict(config_dict.get("additional_params", {})),
            )
        except Exception as exc:
            logger.error(
                "Ошибка создания конфигурации источника",
                extra={"event": "source_config_error", "error": str(exc)},
            )
            return None

    @staticmethod
    def create_from_dict(config_dict: dict[str, Any]) -> StreamReader | None:
        config = VideoSourceFactory.config_from_dict(config_dict)
        if config is None:
            return None
        return VideoSourceFactory.create_source(config)


class CameraManager:
    """Менеджер нескольких источников и цепочки лёгкой обработки кадров."""

    def __init__(self) -> None:
        self.sources: dict[str, StreamReader] = {}
        self.lock = threading.RLock()
        self.running = False
        self.frame_handlers: list[Callable[[FrameData], None]] = []
        self.frame_processors: list[FrameProcessor] = [ScenePreprocessor()]
        self.stats_interval = 5.0
        self.last_stats_time = time.time()
        self._monitor_thread: threading.Thread | None = None

    def add_source(self, config: VideoSourceConfig) -> bool:
        with self.lock:
            if config.source_id in self.sources:
                logger.warning(
                    "Источник уже существует",
                    extra={"event": "source_duplicate", "source_id": config.source_id},
                )
                return False

            reader = VideoSourceFactory.create_source(config)
            if reader is None:
                return False

            reader.register_frame_callback(self._dispatch_frame_handlers)
            self.sources[config.source_id] = reader

            if self.running:
                reader.start_capture()

            logger.info(
                "Источник зарегистрирован",
                extra={
                    "event": "source_registered",
                    "source_id": config.source_id,
                    "camera_id": config.camera_id,
                    "source_type": config.source_type.value,
                },
            )

            return True

    def remove_source(self, source_id: str) -> None:
        with self.lock:
            reader = self.sources.pop(source_id, None)
        if reader is not None:
            reader.stop_capture()
            logger.info("Источник удален", extra={"event": "source_removed", "source_id": source_id})

    def has_source(self, source_id: str) -> bool:
        with self.lock:
            return source_id in self.sources

    def start_source(self, source_id: str) -> bool:
        with self.lock:
            reader = self.sources.get(source_id)
        if reader is None:
            return False
        reader.start_capture()
        return True

    def stop_source(self, source_id: str) -> bool:
        with self.lock:
            reader = self.sources.get(source_id)
        if reader is None:
            return False
        reader.stop_capture()
        return True

    def start_all(self) -> None:
        with self.lock:
            if self.running:
                return
            self.running = True
            readers = list(self.sources.values())

        for reader in readers:
            reader.start_capture()

        self._monitor_thread = threading.Thread(target=self._monitor_stats, name="camera-manager-monitor", daemon=True)
        self._monitor_thread.start()

    def stop_all(self) -> None:
        with self.lock:
            self.running = False
            readers = list(self.sources.values())

        for reader in readers:
            reader.stop_capture()

    def get_frame(self, source_id: str, timeout: float = 1.0) -> FrameData | None:
        with self.lock:
            reader = self.sources.get(source_id)
        if reader is None:
            return None
        return reader.get_frame(timeout)

    def get_all_frames(self, timeout: float = 0.1) -> dict[str, FrameData | None]:
        with self.lock:
            items = list(self.sources.items())
        return {source_id: reader.get_frame(timeout) for source_id, reader in items}

    def register_frame_handler(self, handler: Callable[[FrameData], None]) -> None:
        self.frame_handlers.append(handler)

    def add_frame_processor(self, processor: FrameProcessor) -> None:
        self.frame_processors.append(processor)

    def get_source_info(self, source_id: str) -> dict[str, Any] | None:
        with self.lock:
            reader = self.sources.get(source_id)
        if reader is None:
            return None
        return {
            "source_id": source_id,
            "config": reader.config.to_dict(),
            "stats": reader.get_stats(),
            "status": reader.status.value,
        }

    def get_all_source_info(self) -> dict[str, dict[str, Any]]:
        with self.lock:
            items = list(self.sources.items())
        return {
            source_id: {
                "source_id": source_id,
                "config": reader.config.to_dict(),
                "stats": reader.get_stats(),
                "status": reader.status.value,
            }
            for source_id, reader in items
        }

    def auto_discover_usb_cameras(self) -> list[dict[str, Any]]:
        discovered: list[dict[str, Any]] = []
        for index in range(10):
            cap = cv2.VideoCapture(index)
            if not cap.isOpened():
                cap.release()
                continue
            ret, frame = cap.read()
            if ret and frame is not None:
                discovered.append(
                    {
                        "camera_index": index,
                        "type": VideoSourceType.USB_CAMERA.value,
                        "source_id": f"usb_camera_{index}",
                        "frame_size": list(frame.shape),
                    }
                )
            cap.release()
        return discovered

    def _dispatch_frame_handlers(self, frame_data: FrameData) -> None:
        processed_frame = frame_data
        for processor in self.frame_processors:
            try:
                processed_frame = processor.process(processed_frame)
            except Exception as exc:
                logger.exception(
                    "Ошибка этапа обработки кадра",
                    extra={"event": "frame_processor_error", "processor": processor.__class__.__name__},
                )

        for handler in self.frame_handlers:
            try:
                handler(processed_frame)
            except Exception as exc:
                logger.exception("Ошибка обработчика кадра", extra={"event": "frame_handler_error"})

    def _monitor_stats(self) -> None:
        while self.running:
            now = time.time()
            if now - self.last_stats_time >= self.stats_interval:
                self._log_stats()
                self.last_stats_time = now
            time.sleep(1.0)

    def _log_stats(self) -> None:
        all_info = self.get_all_source_info()
        total_frames = 0
        total_dropped = 0
        active_sources = 0
        for info in all_info.values():
            stats = info["stats"]
            total_frames += int(stats.get("frames_received", 0))
            total_dropped += int(stats.get("frames_dropped", 0))
            if stats.get("running"):
                active_sources += 1
        logger.info(
            "Статистика CameraManager",
            extra={
                "event": "camera_manager_stats",
                "active_sources": active_sources,
                "total_sources": len(all_info),
                "frames_received": total_frames,
                "frames_dropped": total_dropped,
            },
        )
