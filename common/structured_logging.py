from __future__ import annotations

import atexit
import contextlib
import contextvars
import json
import logging
import os
import queue
import sys
import threading
import traceback
from datetime import datetime, timezone
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from typing import Any, Iterator
from uuid import uuid4

_STANDARD_ATTRS = set(logging.makeLogRecord({}).__dict__.keys()) | {"message", "asctime"}
_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar("structured_log_context", default={})
_listener: QueueListener | None = None
_configured_service: str | None = None
_fallback_logger: logging.Logger | None = None
_original_record_factory = logging.getLogRecordFactory()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": getattr(record, "service", _configured_service or "app"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "event": getattr(record, "event", None) or record.name,
        }

        trace_id = getattr(record, "trace_id", None)
        if trace_id:
            payload["trace_id"] = trace_id

        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key.startswith("_"):
                continue
            if key in {"service", "event", "trace_id"} and value is None:
                continue
            payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, ensure_ascii=False, default=_json_default)


class ContextFilter(logging.Filter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = getattr(record, "service", self.service_name)
        context = _context.get()
        for key, value in context.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        if not hasattr(record, "trace_id") and context.get("trace_id"):
            record.trace_id = context["trace_id"]
        return True


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def _parse_level(level: str | int | None) -> int:
    if isinstance(level, int):
        return level
    value = level or os.getenv("LOG_LEVEL", "INFO")
    return getattr(logging, str(value).upper(), logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def new_trace_id() -> str:
    return uuid4().hex


def bind_log_context(**kwargs: Any) -> contextvars.Token[dict[str, Any]]:
    context = dict(_context.get())
    context.update({key: value for key, value in kwargs.items() if value is not None})
    return _context.set(context)


def reset_log_context(token: contextvars.Token[dict[str, Any]]) -> None:
    _context.reset(token)


@contextlib.contextmanager
def logging_context(**kwargs: Any) -> Iterator[None]:
    token = bind_log_context(**kwargs)
    try:
        yield
    finally:
        reset_log_context(token)


def setup_logging(service_name: str, *, level: str | int | None = None) -> logging.Logger:
    global _listener, _configured_service, _fallback_logger

    if _listener is not None and _configured_service == service_name:
        return logging.getLogger(service_name)

    resolved_level = _parse_level(level)
    log_queue: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(resolved_level)
    stdout_handler.setFormatter(JsonFormatter())
    stdout_handler.addFilter(ContextFilter(service_name))

    handlers: list[logging.Handler] = [stdout_handler]

    fallback_file = os.getenv("LOG_FALLBACK_FILE")
    if fallback_file:
        fallback_handler = RotatingFileHandler(
            fallback_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fallback_handler.setLevel(logging.ERROR)
        fallback_handler.setFormatter(JsonFormatter())
        fallback_handler.addFilter(ContextFilter(service_name))
        handlers.append(fallback_handler)

    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)
    root_logger.handlers.clear()
    logging.setLogRecordFactory(_build_record_factory(service_name))
    root_logger.addHandler(QueueHandler(log_queue))

    _listener = QueueListener(log_queue, *handlers, respect_handler_level=True)
    _listener.start()
    _configured_service = service_name
    _fallback_logger = logging.getLogger(service_name)

    _install_exception_hooks(_fallback_logger)
    atexit.register(_shutdown_listener)
    return _fallback_logger


def _build_record_factory(service_name: str):
    def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = _original_record_factory(*args, **kwargs)
        context = _context.get()
        if not hasattr(record, "service"):
            record.service = service_name
        for key, value in context.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        if context.get("trace_id") and not hasattr(record, "trace_id"):
            record.trace_id = context["trace_id"]
        return record

    return record_factory


def _shutdown_listener() -> None:
    global _listener
    if _listener is not None:
        _listener.stop()
        _listener = None


def _install_exception_hooks(logger: logging.Logger) -> None:
    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.error(
            "Unhandled exception",
            extra={
                "event": "unhandled_exception",
                "error_type": getattr(exc_type, "__name__", str(exc_type)),
                "error": str(exc_value),
                "traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            },
        )

    def handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        logger.error(
            "Unhandled thread exception",
            extra={
                "event": "unhandled_thread_exception",
                "thread_name": args.thread.name if args.thread else None,
                "error_type": getattr(args.exc_type, "__name__", str(args.exc_type)),
                "error": str(args.exc_value),
                "traceback": "".join(
                    traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
                ),
            },
        )

    sys.excepthook = handle_exception
    if hasattr(threading, "excepthook"):
        threading.excepthook = handle_thread_exception
