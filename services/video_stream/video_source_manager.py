from __future__ import annotations

import cv2

from common.structured_logging import get_logger, setup_logging
from .camera_manager import CameraManager, VideoSourceFactory
from .models import ConnectionStatus, FrameData, VideoSourceConfig, VideoSourceType
from .preprocessor import ScenePreprocessor, SceneScore
from .stream_reader import StreamReader

logger = get_logger(__name__)

VideoSource = StreamReader
MultiSourceManager = CameraManager


def _demo_configs() -> list[VideoSourceConfig]:
    """Конфигурации для ручной графической проверки модуля."""

    return [
        VideoSourceConfig(
            source_type=VideoSourceType.USB_CAMERA,
            source_uri="",
            source_id="usb_camera_0",
            camera_id=0,
            frame_width=1280,
            frame_height=720,
            fps=30,
        ),
        VideoSourceConfig(
            source_type=VideoSourceType.IP_CAMERA_RTSP,
            source_uri="rtsp://192.168.0.103:8080/h264_pcm.sdp",
            source_id="phone_cam",
            fps=10,
            frame_width=1280,
            frame_height=720,
        ),
    ]


def _run_graphical_demo() -> None:
    """Ручной запуск модуля для локальной проверки потока и предобработки."""

    setup_logging("video_stream_demo")
    manager = CameraManager()

    for config in _demo_configs():
        added = manager.add_source(config)
        if not added:
            logger.warning("Не удалось добавить тестовый источник %s", config.source_id)

    manager.start_all()

    try:
        while True:
            frames = manager.get_all_frames(timeout=0.05)
            for source_id, frame_data in frames.items():
                if frame_data is None:
                    continue

                frame = frame_data.frame.copy()
                scene = frame_data.metadata.get("scene", {})
                scene_level = scene.get("level", "unknown")
                scene_score = scene.get("score", 0.0)
                anomaly_score = scene.get("anomaly_score", 0.0)
                event_state = scene.get("event_state", "unknown")

                cv2.putText(
                    frame,
                    f"{source_id} #{frame_data.frame_number}",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
                cv2.putText(
                    frame,
                    f"scene={scene_level} score={scene_score:.2f}",
                    (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 200, 255),
                    2,
                )
                cv2.putText(
                    frame,
                    f"event={event_state} anomaly={anomaly_score:.2f}",
                    (20, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 200, 0),
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
