"""Minimal logger helper matching :mod:`celery.utils.log`."""

from __future__ import annotations

import logging
from typing import Any


def get_task_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
