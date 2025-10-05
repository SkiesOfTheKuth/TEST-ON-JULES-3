"""Simplified pydantic-settings compatibility layer."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel

__all__ = ["BaseSettings", "SettingsConfigDict"]


class BaseSettings(BaseModel):
    def __init__(self, _env_file: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)


def SettingsConfigDict(**kwargs: Any) -> Dict[str, Any]:
    return dict(kwargs)
