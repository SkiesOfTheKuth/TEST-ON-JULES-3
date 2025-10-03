"""Logging helpers for structured JSON output without external deps."""

from __future__ import annotations

import json
import logging
from typing import Any


class JsonFormatter(logging.Formatter):
    """A minimal JSON formatter compatible with python-json-logger output."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - short override
        payload: dict[str, Any] = {
            "asctime": self.formatTime(record, self.datefmt),
            "levelname": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "extra") and isinstance(record.extra, dict):
            payload.update(record.extra)

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in payload:
                continue
            if key in {"msg", "args", "levelname", "levelno", "pathname", "filename", "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated", "thread", "threadName", "processName", "process", "asctime"}:
                continue
            payload[key] = value

        return json.dumps(payload, ensure_ascii=False)


__all__ = ["JsonFormatter"]
