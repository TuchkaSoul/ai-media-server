from __future__ import annotations

import threading
import time
from typing import Any, Callable

import cv2
import numpy as np

from common.structured_logging import get_logger
from .frame_queue import FrameBuffer
from .models import ConnectionStatus, FrameData, VideoSourceConfig, VideoSourceType

logger = get_logger(__name__)


class StreamReader:
    """
    Считыватель видеопотока с нормализацией кадров.

    Поддерживаемые форматы:
    - webcam / usb camera;
    - RTSP;
    - видеофайл;
    - HTTP/MJPEG/HLS как generic-URI через backend OpenCV, если он доступен.
    """

    def __init__(self, config: VideoSourceConfig):
        self.config = config
        self.status = ConnectionStatus.DISCONNECTED
        self.frame_buffer = FrameBuffer(config.buffer_size)
        self.frame_callbacks: list[Callable[[FrameData], None]] = []
        self.lock = threading.RLock()
        self.thread: threading.Thread | None = None
        self.cap: cv2.VideoCapture | None = None
        self.running = False
        self.frame_count = 0
        self.last_frame_time = 0.0
        self.last_read_at = 0.0
        self.last_error: str | None = None
        self._fps_calc_time = time.monotonic()
        self._fps_calc_frames = 0
        self._source_exhausted = False
        self.stats = {
            "frames_received": 0,
            "frames_dropped": 0,
            "connection_errors": 0,
            "reconnect_attempts": 0,
            "avg_fps": 0.0,
        }

    def register_frame_callback(self, callback: Callable[[FrameData], None]) -> None:
        self.frame_callbacks.append(callback)

    def connect(self) -> bool:
        with self.lock:
            self._release_capture()
            self.status = ConnectionStatus.CONNECTING
            self.last_error = None

            try:
                source = self._build_capture_source()
            except Exception as exc:
                self.status = ConnectionStatus.ERROR
                self.last_error = str(exc)
                logger.error(
                    "Ошибка построения источника",
                    extra={"event": "source_build_error", "source_id": self.config.source_id, "error": str(exc)},
                )
                return False

            backend = self._select_backend()
            cap = cv2.VideoCapture(source) if backend is None else cv2.VideoCapture(source, backend)

            if not cap or not cap.isOpened():
                self.status = ConnectionStatus.ERROR
                self.last_error = f"Не удалось открыть источник {self.config.source_id}"
                logger.error(
                    self.last_error,
                    extra={"event": "source_open_failed", "source_id": self.config.source_id},
                )
                if cap:
                    cap.release()
                return False

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)
            cap.set(cv2.CAP_PROP_FPS, self.config.fps)
            if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
                cap.set(cv2.CAP_PROP_BUFFERSIZE, min(4, max(1, self.config.buffer_size)))
            if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(self.config.timeout_sec * 1000))
            if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(self.config.timeout_sec * 1000))

            self.cap = cap
            self.status = ConnectionStatus.CONNECTED
            self._source_exhausted = False
            logger.info(
                "Подключен источник",
                extra={
                    "event": "camera_connected",
                    "source_id": self.config.source_id,
                    "camera_id": self.config.camera_id,
                    "source_type": self.config.source_type.value,
                    "fps_target": self.config.fps,
                },
            )
            return True

    def disconnect(self) -> None:
        with self.lock:
            self.running = False
            self._release_capture()
            self.status = ConnectionStatus.DISCONNECTED

    def start_capture(self) -> None:
        with self.lock:
            if self.running:
                return
            if not self.connect():
                return
            self.running = True
            self.thread = threading.Thread(
                target=self._capture_loop,
                name=f"stream-reader-{self.config.source_id}",
                daemon=True,
            )
            self.thread.start()

    def stop_capture(self) -> None:
        with self.lock:
            self.running = False
        if self.thread and self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=2.0)
        with self.lock:
            self._release_capture()
            self.status = ConnectionStatus.STOPPED

    def get_frame(self, timeout: float = 1.0) -> FrameData | None:
        return self.frame_buffer.get(timeout)

    def clear_queue(self) -> None:
        self.frame_buffer.clear()

    def get_stats(self) -> dict[str, Any]:
        with self.lock:
            return {
                **self.stats,
                "queue_size": self.frame_buffer.qsize(),
                "status": self.status.value,
                "frame_count": self.frame_count,
                "running": self.running,
                "last_frame_time": self.last_frame_time,
                "last_error": self.last_error,
                "source_exhausted": self._source_exhausted,
            }

    def _capture_loop(self) -> None:
        frame_interval = 1.0 / max(1, self.config.fps)

        while self.running:
            ret, frame = self._read_frame()

            if ret and frame is not None:
                if self._should_emit_frame(frame_interval):
                    frame_data = self._normalize_frame(frame)
                    self._publish_frame(frame_data)
                continue

            if not self.running:
                break

            if self._is_reconnectable():
                if not self._reconnect():
                    logger.error(
                        "Исчерпаны попытки переподключения",
                        extra={"event": "reconnect_exhausted", "source_id": self.config.source_id},
                    )
                    with self.lock:
                        self.running = False
                        self.status = ConnectionStatus.ERROR
                    break
                continue

            if self._is_video_file():
                with self.lock:
                    self._source_exhausted = True
                    self.running = False
                    self.status = ConnectionStatus.STOPPED
                break

            with self.lock:
                self.stats["connection_errors"] += 1
                self.status = ConnectionStatus.ERROR
            time.sleep(self.config.reconnect_delay)

    def _read_frame(self) -> tuple[bool, np.ndarray | None]:
        with self.lock:
            cap = self.cap

        if cap is None or not cap.isOpened():
            return False, None

        ret, frame = cap.read()
        if ret:
            self.last_read_at = time.time()
            return True, frame

        with self.lock:
            self.stats["connection_errors"] += 1
        return False, None

    def _should_emit_frame(self, frame_interval: float) -> bool:
        if self.last_frame_time <= 0:
            return True
        return (time.time() - self.last_frame_time) >= frame_interval

    def _normalize_frame(self, frame: np.ndarray) -> FrameData:
        if frame.shape[1] != self.config.frame_width or frame.shape[0] != self.config.frame_height:
            frame = cv2.resize(frame, (self.config.frame_width, self.config.frame_height))

        timestamp = time.time()
        return FrameData(
            frame=frame,
            timestamp=timestamp,
            frame_number=self.frame_count,
            source_id=self.config.source_id,
            metadata={
                "camera_id": self.config.source_id,
                "source_type": self.config.source_type.value,
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
                "fps_limit": self.config.fps,
            },
        )

    def _publish_frame(self, frame_data: FrameData) -> None:
        buffered = self.frame_buffer.put_latest(frame_data)
        if not buffered:
            self.stats["frames_dropped"] += 1
            logger.warning(
                "Кадр отброшен из-за переполнения буфера",
                extra={
                    "event": "frame_dropped",
                    "source_id": self.config.source_id,
                    "camera_id": self.config.camera_id,
                    "frame_id": frame_data.frame_number,
                },
            )
            return

        self.stats["frames_dropped"] = self.frame_buffer.dropped_frames
        self.stats["frames_received"] += 1
        self.frame_count += 1
        self.last_frame_time = frame_data.timestamp

        if self.frame_count % 30 == 0:
            self._update_fps_stats()

        for callback in self.frame_callbacks:
            try:
                callback(frame_data)
            except Exception as exc:
                logger.exception(
                    "Ошибка frame callback",
                    extra={"event": "frame_callback_error", "source_id": self.config.source_id},
                )

    def _update_fps_stats(self) -> None:
        now = time.monotonic()
        elapsed = now - self._fps_calc_time
        frames_delta = self.frame_count - self._fps_calc_frames
        if elapsed > 0 and frames_delta >= 0:
            self.stats["avg_fps"] = frames_delta / elapsed
            self._fps_calc_time = now
            self._fps_calc_frames = self.frame_count
            logger.info(
                "Обновлена статистика потока",
                extra={
                    "event": "capture_stats",
                    "source_id": self.config.source_id,
                    "camera_id": self.config.camera_id,
                    "fps_actual": round(self.stats["avg_fps"], 2),
                    "frames_received": self.stats["frames_received"],
                    "frames_dropped": self.stats["frames_dropped"],
                },
            )

    def _reconnect(self) -> bool:
        for attempt in range(1, max(1, self.config.reconnect_attempts) + 1):
            with self.lock:
                if not self.running:
                    return False
                self.status = ConnectionStatus.RECONNECTING
                self.stats["reconnect_attempts"] += 1

            logger.warning(
                "Переподключение источника",
                extra={
                    "event": "camera_reconnect_attempt",
                    "source_id": self.config.source_id,
                    "camera_id": self.config.camera_id,
                    "attempt": attempt,
                    "attempts_total": self.config.reconnect_attempts,
                },
            )
            time.sleep(self.config.reconnect_delay)
            if self.connect():
                return True

        return False

    def _build_capture_source(self) -> str | int:
        if self.config.source_type in {VideoSourceType.USB_CAMERA, VideoSourceType.WEB_CAMERA}:
            if self.config.camera_id is not None:
                return int(self.config.camera_id)
            if self.config.source_uri.strip():
                return int(self.config.source_uri)
            return 0

        if self.config.source_type == VideoSourceType.IP_CAMERA_RTSP:
            return self._build_rtsp_url()

        if self.config.source_type in {
            VideoSourceType.VIDEO_FILE,
            VideoSourceType.IP_CAMERA_HTTP,
            VideoSourceType.MJPEG_STREAM,
            VideoSourceType.HLS_STREAM,
            VideoSourceType.CUSTOM,
        }:
            return self.config.source_uri

        raise ValueError(f"Неподдерживаемый тип источника: {self.config.source_type.value}")

    def _build_rtsp_url(self) -> str:
        uri = self.config.source_uri.strip()
        if uri.startswith("rtsp://"):
            return uri

        if self.config.rtsp_username and self.config.rtsp_password and "@" not in uri:
            return f"rtsp://{self.config.rtsp_username}:{self.config.rtsp_password}@{uri}"
        return f"rtsp://{uri}"

    def _select_backend(self) -> int | None:
        if self.config.source_type in {
            VideoSourceType.IP_CAMERA_RTSP,
            VideoSourceType.HLS_STREAM,
            VideoSourceType.MJPEG_STREAM,
            VideoSourceType.IP_CAMERA_HTTP,
        } and hasattr(cv2, "CAP_FFMPEG"):
            return cv2.CAP_FFMPEG
        return None

    def _is_reconnectable(self) -> bool:
        return self.config.source_type in {
            VideoSourceType.IP_CAMERA_RTSP,
            VideoSourceType.IP_CAMERA_HTTP,
            VideoSourceType.MJPEG_STREAM,
            VideoSourceType.HLS_STREAM,
            VideoSourceType.CUSTOM,
        }

    def _is_video_file(self) -> bool:
        return self.config.source_type == VideoSourceType.VIDEO_FILE

    def _release_capture(self) -> None:
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                logger.debug(
                    "Не удалось корректно освободить capture",
                    extra={"event": "capture_release_failed", "source_id": self.config.source_id},
                    exc_info=True,
                )
        self.cap = None
