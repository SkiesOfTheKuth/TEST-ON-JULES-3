"""Configuration for the safe evaluator service."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class EvaluatorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVALUATOR_", env_file=".env.development", env_file_encoding="utf-8")

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
    for candidate in (".env.development", ".env"):
        path = Path(candidate)
        if path.exists():
            return path
    return None
