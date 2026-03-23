from __future__ import annotations

from common.structured_logging import get_logger

from .models import ProcessedFrame

logger = get_logger(__name__)


class DebugConsumer:
    """Минимальный consumer, замыкающий pipeline без внешних зависимостей."""

    def handle(self, frame: ProcessedFrame) -> None:
        print(frame.scene_score)
        logger.info(
            "Processed frame",
            extra={
                "event": "debug_consumer_frame",
                "camera_id": frame.camera_id,
                "frame_number": frame.frame_number,
                "scene_score": frame.scene_score,
                "anomaly_score": frame.anomaly_score,
                "motion_score": frame.motion_score,
                "is_event": frame.is_event,
            },
        )
