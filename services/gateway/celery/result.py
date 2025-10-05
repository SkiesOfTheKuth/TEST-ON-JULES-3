"""Subset of :mod:`celery.result` used in tests."""

from __future__ import annotations

from typing import Any, Optional


class EagerResult:
    """Mimics Celery's eager result object for synchronous execution."""

    def __init__(self, value: Any, successful: bool, exception: Optional[BaseException] = None) -> None:
        self._value = value
        self._exception = exception
        self.successful = successful

    def get(self, timeout: Optional[float] = None) -> Any:  # noqa: ARG002 - compatibility
        if self._exception is not None:
            raise self._exception
        return self._value


__all__ = ["EagerResult"]
