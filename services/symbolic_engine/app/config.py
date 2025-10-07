from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SymbolicSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SYMBOLIC_", env_file=None, extra="ignore")

    sandbox_timeout_seconds: float = 5.0
    sandbox_memory_mb: int = 256
    allowed_functions: List[str] = []
    enable_numba: bool = False

    @field_validator("allowed_functions", mode="before")
    @classmethod
    def _split_allowed(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if value is None:
            return []
        return list(value)


settings = SymbolicSettings()
