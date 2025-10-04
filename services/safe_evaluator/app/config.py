"""Configuration for the safe evaluator service."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class EvaluatorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EVALUATOR_",
        env_file_encoding="utf-8",
    )

    host: str = "0.0.0.0"
    port: int = 50051
    max_runtime_seconds: float = 0.25
    max_result_magnitude: float = 1e12
    max_memory_bytes: int = 64 * 1024 * 1024
    otlp_endpoint: Optional[str] = None
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> EvaluatorSettings:
    return EvaluatorSettings(_env_file=_resolve_env_file())


def _resolve_env_file() -> Optional[Path]:
    explicit = os.getenv("EVALUATOR_ENV_FILE")
    if explicit:
        path = Path(explicit)
        if path.exists():
            return path

    env_name = os.getenv("EVALUATOR_ENVIRONMENT") or os.getenv("ENVIRONMENT")
    candidates: list[str] = []
    if env_name:
        candidates.append(f".env.{env_name.lower()}")
    candidates.extend([".env.development", ".env"])

    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None
