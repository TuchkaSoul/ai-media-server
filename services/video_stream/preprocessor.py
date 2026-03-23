from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from .models import FrameData


@dataclass(slots=True)
class SceneScore:
    """Результат быстрой оценки важности сцены."""

    score: float
    motion_score: float
    edge_density: float
    brightness_score: float
    faces_count: int
    level: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "motion_score": self.motion_score,
            "edge_density": self.edge_density,
            "brightness_score": self.brightness_score,
            "faces_count": self.faces_count,
            "level": self.level,
        }


class ScenePreprocessor:
    """
    Лёгкий предобработчик для первичной оценки важности сцены.

    Он нужен перед тяжёлой аналитикой, чтобы быстро понять,
    какие кадры и сцены стоит обрабатывать дальше с большим приоритетом.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._previous_gray_by_source: dict[str, np.ndarray] = {}
        self._face_detector = self._build_face_detector()

    def process(self, frame_data: FrameData) -> FrameData:
        gray = cv2.cvtColor(frame_data.frame, cv2.COLOR_BGR2GRAY)
        gray_small = cv2.resize(gray, (320, 180))

        with self._lock:
            previous_gray = self._previous_gray_by_source.get(frame_data.source_id)
            self._previous_gray_by_source[frame_data.source_id] = gray_small

        motion_score = self._calculate_motion_score(gray_small, previous_gray)
        edge_density = self._calculate_edge_density(gray_small)
        brightness_score = self._calculate_brightness_score(gray_small)
        faces_count = self._detect_faces(gray_small)
        score = self._combine_scores(motion_score, edge_density, brightness_score, faces_count)
        level = self._to_level(score)

        frame_data.metadata["scene"] = SceneScore(
            score=score,
            motion_score=motion_score,
            edge_density=edge_density,
            brightness_score=brightness_score,
            faces_count=faces_count,
            level=level,
        ).to_dict()
        return frame_data

    @staticmethod
    def _calculate_motion_score(current_gray: np.ndarray, previous_gray: np.ndarray | None) -> float:
        if previous_gray is None:
            return 0.0

        delta = cv2.absdiff(previous_gray, current_gray)
        _, threshold = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)
        motion_ratio = float(np.count_nonzero(threshold)) / float(threshold.size)
        return min(1.0, motion_ratio * 8.0)

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
    def _combine_scores(motion_score: float, edge_density: float, brightness_score: float, faces_count: int) -> float:
        face_score = min(1.0, faces_count / 2.0)
        score = motion_score * 0.5 + edge_density * 0.2 + brightness_score * 0.1 + face_score * 0.2
        return round(max(0.0, min(1.0, score)), 4)

    @staticmethod
    def _to_level(score: float) -> str:
        if score >= 0.75:
            return "high"
        if score >= 0.4:
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
