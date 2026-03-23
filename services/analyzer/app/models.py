from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SemanticDecision:
    scene_label: str
    description: str
    importance: float
    scene_change: bool
    keyframe: dict[str, Any]
    compression: dict[str, Any]
    detections: list[dict[str, Any]]
    event: dict[str, Any]
