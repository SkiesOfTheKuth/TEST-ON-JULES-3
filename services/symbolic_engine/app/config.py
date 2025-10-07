"""Configuration utilities for the Symbolic Engine service."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Symbolic Engine API."""

    app_name: str = "symbolic-engine"
    sandbox_timeout_seconds: float = 2.5
    sandbox_memory_limit_mb: int = 256
    sandbox_cpu_time_seconds: int = 2
    sandbox_allowed_modules: tuple[str, ...] = (
        "sympy",
        "mpmath",
        "math",
        "decimal",
    )
    sandbox_blocked_modules: tuple[str, ...] = (
        "os",
        "subprocess",
        "socket",
        "pathlib",
        "shutil",
    )
    enable_numba_acceleration: bool = False
    default_codegen_target: Literal["c", "python", "llvm"] = "c"

    model_config = SettingsConfigDict(env_prefix="SYMBOLIC_ENGINE_", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
