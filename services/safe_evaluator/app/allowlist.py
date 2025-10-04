"""Allow list management for the evaluator sandbox."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, Optional, Set

from calculator_core import default_allowlist, filter_allowlist

logger = logging.getLogger(__name__)


class AllowListError(RuntimeError):
    """Raised when the allow list configuration cannot be loaded."""


@dataclass(slots=True)
class AllowListSnapshot:
    symbols: Dict[str, object]
    names: Set[str]


class AllowListManager:
    """Load the allow list from disk and refresh when it changes."""

    def __init__(self, path: Optional[Path]) -> None:
        self._path = path
        self._lock = Lock()
        self._symbols: Dict[str, object] = default_allowlist()
        self._names: Set[str] = set(self._symbols)
        self._mtime: float | None = None

        if self._path is not None:
            self._path = self._path.expanduser().resolve()

    def snapshot(self) -> AllowListSnapshot:
        self._refresh_if_needed()
        with self._lock:
            return AllowListSnapshot(symbols=dict(self._symbols), names=set(self._names))

    def _refresh_if_needed(self) -> None:
        if self._path is None:
            return

        try:
            stat = self._path.stat()
        except FileNotFoundError:
            with self._lock:
                if self._mtime is not None:
                    logger.warning(
                        "Allow list file %s disappeared; reverting to defaults", self._path
                    )
                self._symbols = default_allowlist()
                self._names = set(self._symbols)
                self._mtime = None
            return

        if self._mtime is not None and stat.st_mtime <= self._mtime:
            return

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - configuration error path
            raise AllowListError(f"Failed to parse allow list JSON: {exc.msg}") from exc

        functions = payload.get("functions")
        if not isinstance(functions, list):
            raise AllowListError("Allow list file must contain a 'functions' array")

        try:
            symbols = filter_allowlist(functions)
        except ValueError as exc:
            raise AllowListError(str(exc)) from exc

        with self._lock:
            self._symbols = symbols
            self._names = set(symbols)
            self._mtime = stat.st_mtime
            logger.info(
                "Loaded allow list", extra={"path": str(self._path), "symbols": sorted(self._names)}
            )


__all__ = ["AllowListError", "AllowListManager", "AllowListSnapshot"]
