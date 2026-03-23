from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from queue import Empty, Full, Queue
from typing import Any, Callable, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class VideoSourceType(Enum):
    """Supported source types for the capture layer."""

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
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"


@dataclass(slots=True)
class VideoSourceConfig:
    """Normalized config for a single camera/stream."""

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
    """Normalized frame payload used by the rest of the system."""

    frame: np.ndarray
    timestamp: float
    frame_number: int
    source_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


class StreamReader:
    """
    Стабильный считыватель кадров для веб-камеры, RTSP и видеофайлов.

    Цели проекта:
    - один считыватель для каждого источника
    - ограниченный буфер кадров
    - Регулирование частоты кадров на уровне захвата
    - нормализация кадров (размер + временная метка + метаданные)
    - повторное подключение для RTSP
    """

    def __init__(self, config: VideoSourceConfig):
        self.config = config
        self.status = ConnectionStatus.DISCONNECTED
        self.frame_queue: Queue[FrameData] = Queue(maxsize=max(1, config.buffer_size))
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

            source = self._build_capture_source()
            backend = self._select_backend()
            if backend is None:
                cap = cv2.VideoCapture(source)
            else:
                cap = cv2.VideoCapture(source, backend)

            if not cap or not cap.isOpened():
                self.status = ConnectionStatus.ERROR
                self.last_error = f"Unable to open source: {self.config.source_id}"
                logger.error(self.last_error)
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
            logger.info("Connected source %s (%s)", self.config.source_id, self.config.source_type.value)
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
        try:
            return self.frame_queue.get(timeout=timeout)
        except Empty:
            return None

    def clear_queue(self) -> None:
        while True:
            try:
                self.frame_queue.get_nowait()
            except Empty:
                return

    def get_stats(self) -> dict[str, Any]:
        with self.lock:
            return {
                **self.stats,
                "queue_size": self.frame_queue.qsize(),
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
            loop_started = time.monotonic()
            ret, frame = self._read_frame()

            if ret and frame is not None:
                if self._should_emit_frame(loop_started, frame_interval):
                    frame_data = self._normalize_frame(frame)
                    self._publish_frame(frame_data)
                continue

            if not self.running:
                break

            if self._is_rtsp():
                if not self._reconnect():
                    logger.error("Reconnect attempts exceeded for %s", self.config.source_id)
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

    def _should_emit_frame(self, loop_started: float, frame_interval: float) -> bool:
        if self.last_frame_time <= 0:
            return True
        return (time.time() - self.last_frame_time) >= frame_interval

    def _normalize_frame(self, frame: np.ndarray) -> FrameData:
        if frame.shape[1] != self.config.frame_width or frame.shape[0] != self.config.frame_height:
            frame = cv2.resize(frame, (self.config.frame_width, self.config.frame_height))

        timestamp = time.time()
        frame_data = FrameData(
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
        return frame_data

    def _publish_frame(self, frame_data: FrameData) -> None:
        try:
            self.frame_queue.put_nowait(frame_data)
        except Full:
            try:
                self.frame_queue.get_nowait()
            except Empty:
                pass
            try:
                self.frame_queue.put_nowait(frame_data)
            except Full:
                self.stats["frames_dropped"] += 1
                return

        self.stats["frames_received"] += 1
        self.frame_count += 1
        self.last_frame_time = frame_data.timestamp

        if self.frame_count % 30 == 0:
            self._update_fps_stats()

        for callback in self.frame_callbacks:
            try:
                callback(frame_data)
            except Exception as exc:
                logger.exception("Frame callback error for %s: %s", self.config.source_id, exc)

    def _update_fps_stats(self) -> None:
        now = time.monotonic()
        elapsed = now - self._fps_calc_time
        frames_delta = self.frame_count - self._fps_calc_frames
        if elapsed > 0 and frames_delta >= 0:
            self.stats["avg_fps"] = frames_delta / elapsed
            self._fps_calc_time = now
            self._fps_calc_frames = self.frame_count

    def _reconnect(self) -> bool:
        for attempt in range(1, max(1, self.config.reconnect_attempts) + 1):
            with self.lock:
                if not self.running:
                    return False
                self.status = ConnectionStatus.RECONNECTING
                self.stats["reconnect_attempts"] += 1

            logger.warning(
                "Reconnecting source %s, attempt %s/%s",
                self.config.source_id,
                attempt,
                self.config.reconnect_attempts,
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

        if self.config.source_type == VideoSourceType.VIDEO_FILE:
            return self.config.source_uri

        raise ValueError(f"Unsupported source type for StreamReader: {self.config.source_type.value}")

    def _build_rtsp_url(self) -> str:
        uri = self.config.source_uri.strip()
        if uri.startswith("rtsp://"):
            return uri

        if self.config.rtsp_username and self.config.rtsp_password and "@" not in uri:
            return f"rtsp://{self.config.rtsp_username}:{self.config.rtsp_password}@{uri}"
        return f"rtsp://{uri}"

    def _select_backend(self) -> int | None:
        if self._is_rtsp() and hasattr(cv2, "CAP_FFMPEG"):
            return cv2.CAP_FFMPEG
        return None

    def _is_rtsp(self) -> bool:
        return self.config.source_type == VideoSourceType.IP_CAMERA_RTSP

    def _is_video_file(self) -> bool:
        return self.config.source_type == VideoSourceType.VIDEO_FILE

    def _release_capture(self) -> None:
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                logger.debug("Capture release failed for %s", self.config.source_id, exc_info=True)
        self.cap = None


VideoSource = StreamReader


class VideoSourceFactory:
    """Compatibility wrapper around the new StreamReader implementation."""

    SUPPORTED_SOURCE_TYPES = {
        VideoSourceType.USB_CAMERA,
        VideoSourceType.WEB_CAMERA,
        VideoSourceType.IP_CAMERA_RTSP,
        VideoSourceType.VIDEO_FILE,
    }

    @staticmethod
    def create_source(config: VideoSourceConfig) -> StreamReader | None:
        if config.source_type not in VideoSourceFactory.SUPPORTED_SOURCE_TYPES:
            logger.error("Unsupported source type: %s", config.source_type.value)
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
            logger.error("Failed to build source config: %s", exc)
            return None

    @staticmethod
    def create_from_dict(config_dict: dict[str, Any]) -> StreamReader | None:
        config = VideoSourceFactory.config_from_dict(config_dict)
        if config is None:
            return None
        return VideoSourceFactory.create_source(config)


class CameraManager:
    """Manager for multiple StreamReader instances."""

    def __init__(self) -> None:
        self.sources: dict[str, StreamReader] = {}
        self.lock = threading.RLock()
        self.running = False
        self.frame_handlers: list[Callable[[FrameData], None]] = []
        self.stats_interval = 5.0
        self.last_stats_time = time.time()
        self._monitor_thread: threading.Thread | None = None

    def add_source(self, config: VideoSourceConfig) -> bool:
        with self.lock:
            if config.source_id in self.sources:
                logger.warning("Source %s already exists", config.source_id)
                return False

            reader = VideoSourceFactory.create_source(config)
            if reader is None:
                return False

            reader.register_frame_callback(self._dispatch_frame_handlers)
            self.sources[config.source_id] = reader

            if self.running:
                reader.start_capture()

            return True

    def remove_source(self, source_id: str) -> None:
        with self.lock:
            reader = self.sources.pop(source_id, None)
        if reader is not None:
            reader.stop_capture()

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
        for handler in self.frame_handlers:
            try:
                handler(frame_data)
            except Exception as exc:
                logger.exception("Camera manager frame handler error: %s", exc)

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
            "CameraManager stats: active=%s/%s frames=%s dropped=%s",
            active_sources,
            len(all_info),
            total_frames,
            total_dropped,
        )


MultiSourceManager = CameraManager


def _demo_configs() -> list[VideoSourceConfig]:
    return [
        VideoSourceConfig(
            source_type=VideoSourceType.USB_CAMERA,
            source_uri="",
            source_id="usb_camera_0",
            camera_id=0,
            frame_width=1280,
            frame_height=720,
            fps=10,
        ),
        VideoSourceConfig(
    source_type=VideoSourceType.IP_CAMERA_RTSP,
    source_uri="rtsp://192.168.0.103:8080/h264_pcm.sdp",
    source_id="phone_cam",
    fps=10,
    frame_width=1280,
    frame_height=720,
)


    ]


def _run_graphical_demo() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    manager = CameraManager()

    for config in _demo_configs():
        added = manager.add_source(config)
        if not added:
            logger.warning("Unable to add demo source %s", config.source_id)

    manager.start_all()

    try:
        while True:
            frames = manager.get_all_frames(timeout=0.05)
            for source_id, frame_data in frames.items():
                if frame_data is None:
                    continue
                frame = frame_data.frame.copy()
                cv2.putText(
                    frame,
                    f"{source_id} #{frame_data.frame_number} {frame_data.timestamp:.3f}",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
                cv2.imshow(f"StreamReader: {source_id}", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        manager.stop_all()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    _run_graphical_demo()
