from __future__ import annotations

from queue import Empty, Full, Queue

from .models import FrameData, ProcessedFrame


class FrameBuffer:
    """
    Потокобезопасный буфер кадров.

    При переполнении удаляется самый старый кадр,
    чтобы система всегда работала с максимально свежим состоянием потока.
    """

    def __init__(self, maxsize: int) -> None:
        self._queue: Queue[FrameData] = Queue(maxsize=max(1, maxsize))
        self.dropped_frames = 0

    def put_latest(self, frame_data: FrameData) -> bool:
        try:
            self._queue.put_nowait(frame_data)
            return True
        except Full:
            try:
                self._queue.get_nowait()
            except Empty:
                pass

            try:
                self._queue.put_nowait(frame_data)
                self.dropped_frames += 1
                return True
            except Full:
                self.dropped_frames += 1
                return False

    def get(self, timeout: float = 1.0) -> FrameData | None:
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None

    def clear(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except Empty:
                return

    def qsize(self) -> int:
        return self._queue.qsize()


class ProcessedFrameQueue:
    """
    Потокобезопасная очередь обработанных кадров.

    Политика переполнения фиксирована: `drop oldest`.
    Это держит consumer ближе к реальному времени и не накапливает устаревшие кадры.
    """

    def __init__(self, maxsize: int) -> None:
        self._queue: Queue[ProcessedFrame] = Queue(maxsize=max(1, maxsize))
        self.dropped_frames = 0

    def put(self, frame: ProcessedFrame) -> bool:
        try:
            self._queue.put_nowait(frame)
            return True
        except Full:
            try:
                self._queue.get_nowait()
            except Empty:
                pass

            try:
                self._queue.put_nowait(frame)
                self.dropped_frames += 1
                return True
            except Full:
                self.dropped_frames += 1
                return False

    def get(self, timeout: float = 1.0) -> ProcessedFrame | None:
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None

    def clear(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except Empty:
                return

    def qsize(self) -> int:
        return self._queue.qsize()
