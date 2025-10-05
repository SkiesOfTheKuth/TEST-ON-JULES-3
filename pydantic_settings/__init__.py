"""Minimal subset of pydantic-settings for offline tests."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class SettingsConfigDict(ConfigDict):
    pass


class BaseSettings(BaseModel):
    def __init__(self, _env_file: Any = None, **data: Any) -> None:  # noqa: D401, ARG002
        super().__init__(**data)


__all__ = ["BaseSettings", "SettingsConfigDict"]
