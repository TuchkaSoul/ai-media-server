from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class PendingFrame:
    camera_id: int
    source_id: str
    frame_data: object


class FrameBatchWriter:
    """Threaded batch writer with size- or time-based flush."""

    def __init__(
        self,
        flush_callback: Callable[[list[PendingFrame]], None],
        *,
        batch_size: int = 50,
        flush_interval: float = 1.0,
    ) -> None:
        self._flush_callback = flush_callback
        self._batch_size = max(1, batch_size)
        self._flush_interval = max(0.05, flush_interval)
        self._buffer: list[PendingFrame] = []
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        with self._condition:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="frame-batch-writer", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._condition:
            self._stop_event.set()
            self._condition.notify_all()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None

    def submit(self, item: PendingFrame) -> None:
        with self._condition:
            self._buffer.append(item)
            if len(self._buffer) >= self._batch_size:
                self._condition.notify_all()

    def _run(self) -> None:
        while True:
            with self._condition:
                should_stop = self._stop_event.is_set()
                if not should_stop and len(self._buffer) < self._batch_size:
                    self._condition.wait(timeout=self._flush_interval)
                    should_stop = self._stop_event.is_set()

                batch = list(self._buffer)
                self._buffer.clear()

            if batch:
                try:
                    self._flush_callback(batch)
                except Exception:
                    logger.exception("Frame batch flush failed", extra={"event": "frame_batch_flush_failed"})

            if should_stop:
                return
