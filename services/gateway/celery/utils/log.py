"""Logging helpers for the Celery stub."""

from __future__ import annotations

import logging


def get_task_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


__all__ = ["get_task_logger"]
