from __future__ import annotations
import threading
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from .models import FrameData


@dataclass(slots=True)
class SceneFeatures:
    motion_score: float
    edge_density: float
    brightness_score: float
    brightness_shift: float
    faces_count: int

    def as_vector(self) -> np.ndarray:
        return np.array(
            [
                self.motion_score,
                self.edge_density,
                self.brightness_score,
                self.brightness_shift,
                min(1.0, self.faces_count / 2.0),
            ],
            dtype=np.float32,
        )


@dataclass(slots=True)
class TemporalState:
    previous_gray: np.ndarray | None = None
    baseline_mean: np.ndarray | None = None
    baseline_var: np.ndarray | None = None
    frames_seen: int = 0
    consecutive_anomaly_frames: int = 0


@dataclass(slots=True)
class SceneScore:
    """Результат лёгкой многоуровневой оценки сцены."""

    score: float
    signal_score: float
    structural_score: float
    anomaly_score: float
    motion_score: float
    edge_density: float
    brightness_score: float
    brightness_shift: float
    faces_count: int
    event_state: str
    level: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "signal_score": self.signal_score,
            "structural_score": self.structural_score,
            "anomaly_score": self.anomaly_score,
            "motion_score": self.motion_score,
            "edge_density": self.edge_density,
            "brightness_score": self.brightness_score,
            "brightness_shift": self.brightness_shift,
            "faces_count": self.faces_count,
            "event_state": self.event_state,
            "level": self.level,
        }


class ScenePreprocessor:
    """
    Лёгкий предобработчик для первичной оценки важности сцены.

    Пайплайн построен как:
    Frame -> Feature Extraction -> Temporal Baseline -> Anomaly Score -> Event Trigger
    """

    _FEATURE_WEIGHTS = np.array([0.45, 0.15, 0.1, 0.2, 0.1], dtype=np.float32)
    _EMA_ALPHA = 0.08
    _WARMUP_FRAMES = 12
    _EPS = 1e-4

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state_by_source: dict[str, TemporalState] = {}
        self._face_detector = self._build_face_detector()

    def process(self, frame_data: FrameData) -> FrameData:
        gray = cv2.cvtColor(frame_data.frame, cv2.COLOR_BGR2GRAY)
        gray_small = cv2.resize(gray, (320, 180))

        with self._lock:
            state = self._state_by_source.setdefault(frame_data.source_id, TemporalState())
            previous_gray = state.previous_gray
            state.previous_gray = gray_small

            features = self._extract_features(gray_small, previous_gray)
            signal_score = self._calculate_signal_score(features)
            structural_score = self._calculate_structural_score(features)
            anomaly_score, event_state = self._calculate_anomaly_score(state, features)
            score = self._combine_scores(signal_score, structural_score, anomaly_score, state.consecutive_anomaly_frames)
            level = self._to_level(score, anomaly_score, state.consecutive_anomaly_frames, event_state)
            self._update_baseline(state, features.as_vector())

        frame_data.metadata["scene"] = SceneScore(
            score=score,
            signal_score=signal_score,
            structural_score=structural_score,
            anomaly_score=anomaly_score,
            motion_score=features.motion_score,
            edge_density=features.edge_density,
            brightness_score=features.brightness_score,
            brightness_shift=features.brightness_shift,
            faces_count=features.faces_count,
            event_state=event_state,
            level=level,
        ).to_dict()
        return frame_data

    def _extract_features(self, gray: np.ndarray, previous_gray: np.ndarray | None) -> SceneFeatures:
        motion_score, brightness_shift = self._calculate_motion_features(gray, previous_gray)
        edge_density = self._calculate_edge_density(gray)
        brightness_score = self._calculate_brightness_score(gray)
        faces_count = self._detect_faces(gray)
        return SceneFeatures(
            motion_score=motion_score,
            edge_density=edge_density,
            brightness_score=brightness_score,
            brightness_shift=brightness_shift,
            faces_count=faces_count,
        )

    @staticmethod
    def _calculate_motion_features(current_gray: np.ndarray, previous_gray: np.ndarray | None) -> tuple[float, float]:
        if previous_gray is None:
            return 0.0, 0.0

        delta = cv2.absdiff(previous_gray, current_gray)
        _, threshold = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)
        motion_ratio = float(np.count_nonzero(threshold)) / float(threshold.size)
        brightness_shift = min(1.0, float(np.mean(delta)) / 32.0)
        return min(1.0, motion_ratio * 8.0), brightness_shift

    @staticmethod
    def _calculate_edge_density(gray: np.ndarray) -> float:
        edges = cv2.Canny(gray, 80, 150)
        density = float(np.count_nonzero(edges)) / float(edges.size)
        return min(1.0, density * 4.0)

    @staticmethod
    def _calculate_brightness_score(gray: np.ndarray) -> float:
        mean_value = float(np.mean(gray)) / 255.0
        return 1.0 - abs(0.5 - mean_value) * 2.0

    def _detect_faces(self, gray: np.ndarray) -> int:
        if self._face_detector is None:
            return 0

        faces = self._face_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(24, 24))
        return int(len(faces))

    @staticmethod
    def _calculate_signal_score(features: SceneFeatures) -> float:
        score = features.motion_score * 0.7 + features.brightness_shift * 0.3
        return round(max(0.0, min(1.0, score)), 4)

    @staticmethod
    def _calculate_structural_score(features: SceneFeatures) -> float:
        face_score = min(1.0, features.faces_count / 2.0)
        score = features.edge_density * 0.65 + face_score * 0.35
        return round(max(0.0, min(1.0, score)), 4)

    def _calculate_anomaly_score(self, state: TemporalState, features: SceneFeatures) -> tuple[float, str]:
        vector = features.as_vector()
        if state.baseline_mean is None or state.baseline_var is None or state.frames_seen < self._WARMUP_FRAMES:
            state.frames_seen += 1
            state.consecutive_anomaly_frames = 0
            return 0.0, "warmup"

        std = np.sqrt(np.maximum(state.baseline_var, self._EPS))
        z_scores = np.abs(vector - state.baseline_mean) / std
        weighted_z = float(np.dot(np.clip(z_scores, 0.0, 4.0) / 4.0, self._FEATURE_WEIGHTS))
        anomaly_score = round(max(0.0, min(1.0, weighted_z)), 4)

        if anomaly_score >= 0.7:
            state.consecutive_anomaly_frames += 1
            if state.consecutive_anomaly_frames >= 3:
                return anomaly_score, "important_event"
            return anomaly_score, "anomaly_detected"

        if anomaly_score >= 0.4 and features.motion_score >= 0.12:
            state.consecutive_anomaly_frames = max(1, state.consecutive_anomaly_frames + 1)
            return anomaly_score, "anomaly_detected"

        state.consecutive_anomaly_frames = 0
        if features.motion_score >= 0.12:
            return anomaly_score, "motion_only"
        return anomaly_score, "normal"

    def _update_baseline(self, state: TemporalState, vector: np.ndarray) -> None:
        if state.baseline_mean is None or state.baseline_var is None:
            state.baseline_mean = vector.copy()
            state.baseline_var = np.full_like(vector, 0.05, dtype=np.float32)
            return

        delta = vector - state.baseline_mean
        state.baseline_mean = (1.0 - self._EMA_ALPHA) * state.baseline_mean + self._EMA_ALPHA * vector
        state.baseline_var = (1.0 - self._EMA_ALPHA) * state.baseline_var + self._EMA_ALPHA * np.square(delta)

    @staticmethod
    def _combine_scores(
        signal_score: float,
        structural_score: float,
        anomaly_score: float,
        consecutive_anomaly_frames: int,
    ) -> float:
        persistence_bonus = min(0.15, consecutive_anomaly_frames * 0.05)
        score = anomaly_score * 0.55 + signal_score * 0.3 + structural_score * 0.15 + persistence_bonus
        return round(max(0.0, min(1.0, score)), 4)

    @staticmethod
    def _to_level(score: float, anomaly_score: float, consecutive_anomaly_frames: int, event_state: str) -> str:
        if event_state == "important_event" or (anomaly_score >= 0.7 and consecutive_anomaly_frames >= 2) or score >= 0.8:
            return "high"
        if event_state in {"anomaly_detected", "motion_only"} or anomaly_score >= 0.4 or score >= 0.4:
            return "medium"
        return "low"

    @staticmethod
    def _build_face_detector():
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            detector = cv2.CascadeClassifier(cascade_path)
            if detector.empty():
                return None
            return detector
        except Exception:
            return None
