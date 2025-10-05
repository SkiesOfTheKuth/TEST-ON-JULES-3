"""Result objects returned by the Celery test stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EagerResult:
    """Subset of :class:`celery.result.EagerResult` used in tests."""

    result: Any | None = None
    exception: BaseException | None = None

    def get(self, timeout: float | None = None) -> Any:
        if self.exception is not None:
            raise self.exception
        return self.result
