"""Time utilities for consistent timezone-aware timestamps."""

from __future__ import annotations

import datetime as dt


def utcnow() -> dt.datetime:
    """Return the current UTC time with timezone information."""
    return dt.datetime.now(dt.timezone.utc)
