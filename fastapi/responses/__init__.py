"""Response helpers for the FastAPI shim."""

from __future__ import annotations

from typing import Any, Dict


class JSONResponse:
    def __init__(self, content: Dict[str, Any]) -> None:
        self.content = content

    def __iter__(self):  # pragma: no cover - minimal compatibility
        yield self.content


__all__ = ["JSONResponse"]
