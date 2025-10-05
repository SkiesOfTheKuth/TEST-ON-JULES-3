"""Resource shim used by observability modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Resource:
    attributes: Dict[str, Any]

    @staticmethod
    def create(attributes: Dict[str, Any]) -> "Resource":
        return Resource(dict(attributes))


__all__ = ["Resource"]
