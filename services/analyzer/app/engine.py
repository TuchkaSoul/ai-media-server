from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING

import numpy as np

from analyzer.app.models import SemanticDecision

if TYPE_CHECKING:
    from video_stream.models import ProcessedFrame


@dataclass(slots=True)
class AnalyzerState:
    last_scene_vector: np.ndarray | None = None
    last_scene_label: str | None = None
    last_keyframe_number: int = -10_000
    last_event_frame: int = -10_000


class SemanticAnalyzer:
    """Легкий семантический анализатор поверх scene preprocessor.

    Не требует тяжелых моделей: использует motion/anomaly/structural сигналы,
    чтобы уже на ingest-этапе получать полезную аналитику для архива и triage.
    """

    def __init__(
        self,
        *,
        keyframe_interval: int = 45,
        event_cooldown_frames: int = 20,
        scene_change_threshold: float = 0.22,
    ) -> None:
        self._state_by_source: dict[str, AnalyzerState] = {}
        self._lock = RLock()
        self._keyframe_interval = max(1, keyframe_interval)
        self._event_cooldown_frames = max(1, event_cooldown_frames)
        self._scene_change_threshold = max(0.05, scene_change_threshold)

    def analyze(self, frame: ProcessedFrame) -> ProcessedFrame:
        metadata = dict(frame.metadata)
        scene = dict(metadata.get("scene") or {})

        motion_score = float(scene.get("motion_score", frame.motion_score))
        anomaly_score = float(scene.get("anomaly_score", frame.anomaly_score))
        scene_score = float(scene.get("score", frame.scene_score))
        edge_density = float(scene.get("edge_density", 0.0))
        brightness_score = float(scene.get("brightness_score", 0.0))
        faces_count = int(scene.get("faces_count", 0))
        level = str(scene.get("level", "low"))

        scene_vector = np.array(
            [
                scene_score,
                motion_score,
                anomaly_score,
                edge_density,
                brightness_score,
                min(1.0, faces_count / 2.0),
            ],
            dtype=np.float32,
        )
        scene_label = self._classify_scene(
            motion_score=motion_score,
            anomaly_score=anomaly_score,
            faces_count=faces_count,
            edge_density=edge_density,
            level=level,
        )

        with self._lock:
            state = self._state_by_source.setdefault(frame.source_id, AnalyzerState())
            scene_change_score = self._scene_distance(scene_vector, state.last_scene_vector)
            scene_change = bool(
                state.last_scene_vector is None
                or scene_change_score >= self._scene_change_threshold
                or state.last_scene_label != scene_label
            )
            keyframe = self._build_keyframe_decision(state, frame, scene_score, anomaly_score, scene_change)
            detections = self._build_detections(
                motion_score=motion_score,
                anomaly_score=anomaly_score,
                faces_count=faces_count,
                scene_label=scene_label,
            )
            event = self._build_event(
                state,
                frame,
                scene_label=scene_label,
                scene_score=scene_score,
                anomaly_score=anomaly_score,
                scene_change=scene_change,
                detections=detections,
            )
            compression = self._build_compression_policy(
                scene_score=scene_score,
                anomaly_score=anomaly_score,
                keyframe=keyframe,
                has_faces=faces_count > 0,
            )
            description = self._describe_scene(
                scene_label=scene_label,
                scene_score=scene_score,
                motion_score=motion_score,
                anomaly_score=anomaly_score,
                faces_count=faces_count,
                scene_change=scene_change,
            )

            state.last_scene_vector = scene_vector
            state.last_scene_label = scene_label
            if keyframe["should_save"]:
                state.last_keyframe_number = frame.frame_number
            if event["should_emit"]:
                state.last_event_frame = frame.frame_number

        decision = SemanticDecision(
            scene_label=scene_label,
            description=description,
            importance=round(max(scene_score, anomaly_score), 4),
            scene_change=scene_change,
            keyframe=keyframe,
            compression=compression,
            detections=detections,
            event=event,
        )

        scene["label"] = decision.scene_label
        scene["scene_change"] = decision.scene_change
        scene["scene_change_score"] = round(scene_change_score, 4)
        metadata["scene"] = scene
        metadata["analysis"] = {
            "description": decision.description,
            "importance": decision.importance,
            "scene_label": decision.scene_label,
            "scene_change": decision.scene_change,
            "scene_change_score": round(scene_change_score, 4),
            "keyframe": decision.keyframe,
            "compression": decision.compression,
            "event": decision.event,
        }
        metadata["descriptions"] = {
            "short": decision.description,
            "operator": self._operator_description(decision, faces_count=faces_count),
        }
        metadata["detections"] = decision.detections
        metadata["keyframe"] = decision.keyframe
        metadata["compression"] = decision.compression

        frame.metadata = metadata
        frame.is_event = frame.is_event or bool(decision.event["should_emit"])
        return frame

    @staticmethod
    def _scene_distance(current: np.ndarray, previous: np.ndarray | None) -> float:
        if previous is None:
            return 1.0
        return float(np.linalg.norm(current - previous) / np.sqrt(current.size))

    @staticmethod
    def _classify_scene(
        *,
        motion_score: float,
        anomaly_score: float,
        faces_count: int,
        edge_density: float,
        level: str,
    ) -> str:
        if anomaly_score >= 0.75 or level == "high":
            return "critical_activity"
        if faces_count > 0 and motion_score >= 0.16:
            return "human_activity"
        if faces_count > 0:
            return "human_presence"
        if motion_score >= 0.3:
            return "dynamic_motion"
        if edge_density < 0.2 and motion_score < 0.08:
            return "static_scene"
        return "background_watch"

    def _build_keyframe_decision(
        self,
        state: AnalyzerState,
        frame: ProcessedFrame,
        scene_score: float,
        anomaly_score: float,
        scene_change: bool,
    ) -> dict[str, object]:
        reasons: list[str] = []
        if state.last_scene_vector is None:
            reasons.append("bootstrap")
        if scene_change:
            reasons.append("scene_change")
        if frame.is_event or anomaly_score >= 0.55:
            reasons.append("event")
        if scene_score >= 0.58:
            reasons.append("importance")
        if frame.frame_number - state.last_keyframe_number >= self._keyframe_interval:
            reasons.append("interval")

        should_save = bool(reasons)
        return {
            "should_save": should_save,
            "reason": reasons[0] if reasons else "skip",
            "reasons": reasons,
            "score": round(max(scene_score, anomaly_score), 4),
        }

    @staticmethod
    def _build_detections(
        *,
        motion_score: float,
        anomaly_score: float,
        faces_count: int,
        scene_label: str,
    ) -> list[dict[str, object]]:
        detections: list[dict[str, object]] = []
        if faces_count > 0:
            detections.append(
                {
                    "label": "face_presence",
                    "confidence": round(min(0.99, 0.6 + faces_count * 0.15), 4),
                    "bbox": None,
                    "attributes": {"count": faces_count, "scene_label": scene_label},
                }
            )
        if motion_score >= 0.15:
            detections.append(
                {
                    "label": "motion_activity",
                    "confidence": round(min(0.99, 0.45 + motion_score * 0.5), 4),
                    "bbox": None,
                    "attributes": {"motion_score": round(motion_score, 4), "scene_label": scene_label},
                }
            )
        if anomaly_score >= 0.4:
            detections.append(
                {
                    "label": "scene_anomaly",
                    "confidence": round(min(0.99, 0.5 + anomaly_score * 0.4), 4),
                    "bbox": None,
                    "attributes": {"anomaly_score": round(anomaly_score, 4), "scene_label": scene_label},
                }
            )
        return detections

    def _build_event(
        self,
        state: AnalyzerState,
        frame: ProcessedFrame,
        *,
        scene_label: str,
        scene_score: float,
        anomaly_score: float,
        scene_change: bool,
        detections: list[dict[str, object]],
    ) -> dict[str, object]:
        cooldown_passed = (frame.frame_number - state.last_event_frame) >= self._event_cooldown_frames
        should_emit = cooldown_passed and (
            frame.is_event or anomaly_score >= 0.55 or (scene_change and scene_score >= 0.35)
        )

        if anomaly_score >= 0.7:
            event_type = "critical_scene_detected"
        elif scene_change and scene_score >= 0.35:
            event_type = "scene_transition_detected"
        elif detections:
            event_type = "activity_detected"
        else:
            event_type = "background_observation"

        return {
            "should_emit": should_emit,
            "event_type": event_type,
            "importance_score": round(max(scene_score, anomaly_score), 4),
            "payload": {
                "scene_label": scene_label,
                "scene_score": round(scene_score, 4),
                "anomaly_score": round(anomaly_score, 4),
                "detection_labels": [item["label"] for item in detections],
            },
        }

    @staticmethod
    def _build_compression_policy(
        *,
        scene_score: float,
        anomaly_score: float,
        keyframe: dict[str, object],
        has_faces: bool,
    ) -> dict[str, object]:
        preserve = bool(keyframe["should_save"]) or anomaly_score >= 0.55 or has_faces
        if preserve:
            strategy = "preserve"
            sample_every = 1
        elif scene_score >= 0.35:
            strategy = "adaptive"
            sample_every = 3
        else:
            strategy = "sparse"
            sample_every = 6

        return {
            "strategy": strategy,
            "sample_every_n_frames": sample_every,
            "preserve": preserve,
            "priority": "high" if preserve else "normal",
        }

    @staticmethod
    def _describe_scene(
        *,
        scene_label: str,
        scene_score: float,
        motion_score: float,
        anomaly_score: float,
        faces_count: int,
        scene_change: bool,
    ) -> str:
        parts: list[str] = []
        label_map = {
            "critical_activity": "обнаружена критичная активность",
            "human_activity": "в кадре активность человека",
            "human_presence": "в кадре присутствует человек",
            "dynamic_motion": "в сцене выраженное движение",
            "static_scene": "сцена стабильна",
            "background_watch": "фоновое наблюдение без выраженного события",
        }
        parts.append(label_map.get(scene_label, "зафиксировано изменение сцены"))
        parts.append(f"важность {scene_score:.2f}")
        if anomaly_score >= 0.4:
            parts.append(f"аномалия {anomaly_score:.2f}")
        if motion_score >= 0.12:
            parts.append(f"движение {motion_score:.2f}")
        if faces_count > 0:
            parts.append(f"лиц: {faces_count}")
        if scene_change:
            parts.append("смена сцены")
        return ", ".join(parts)

    @staticmethod
    def _operator_description(decision: SemanticDecision, *, faces_count: int) -> str:
        focus = "сохранить в архив как ключевой кадр" if decision.keyframe["should_save"] else "достаточно редкого сэмплирования"
        people = f", лиц в кадре: {faces_count}" if faces_count > 0 else ""
        return f"{decision.description}; режим компрессии: {decision.compression['strategy']}{people}; {focus}."
