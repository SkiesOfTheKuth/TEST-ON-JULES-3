"""Configuration for the gateway service."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseModel):
    url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 300
    cache_namespace: str = "cache"
    rate_limit_window_seconds: int = 60
    rate_limit_requests: int = 10
    rate_counter_ttl_seconds: int = 60
    rate_namespace: str = "rate"
    limiter_namespace: str = "limiter"


class DatabaseSettings(BaseModel):
    url: str = "postgresql+asyncpg://calculator:calculator@localhost:5432/calculator"
    pool_size: int = 5
    pool_timeout: int = 10


class EvaluatorSettings(BaseModel):
    host: str = "safe-evaluator"
    port: int = 50051
    deadline_ms: int = 250
    use_tls: bool = False
    root_cert_path: Optional[Path] = None
    client_cert_path: Optional[Path] = None
    client_key_path: Optional[Path] = None


class ObservabilitySettings(BaseModel):
    service_name: str = "calculator-gateway"
    otlp_endpoint: Optional[str] = None
    metrics_namespace: str = "calculator_gateway"


class QuotaSettings(BaseModel):
    limit: int = 1000
    window_seconds: int = 60


class JobSettings(BaseModel):
    default_ttl_seconds: int = 3600
    max_queue_size: int = 1000
    max_concurrency: int = 10
    priority_levels: int = 3
    queue_name: str = "calculator-jobs"
    cache_namespace: str = "jobs"
    rate_limit_requests: int = 5
    rate_limit_window_seconds: int = 1
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0
    rate_namespace: str = "job_rate"
    notification_namespace: str = "job_events"


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
    )

    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    redis: RedisSettings = RedisSettings()
    database: DatabaseSettings = DatabaseSettings()
    evaluator: EvaluatorSettings = EvaluatorSettings()
    observability: ObservabilitySettings = ObservabilitySettings()
    quota: QuotaSettings = QuotaSettings()
    job: JobSettings = JobSettings()
    audit_batch_size: int = 100
    cache_pure_results: bool = True
    allowed_origins: list[str] = ["*"]


@lru_cache(maxsize=1)
def get_settings() -> GatewaySettings:
    return GatewaySettings(_env_file=_resolve_env_file())


def _resolve_env_file() -> Optional[Path]:
    explicit = os.getenv("GATEWAY_ENV_FILE")
    if explicit:
        path = Path(explicit)
        if path.exists():
            return path

    env_name = os.getenv("GATEWAY_ENVIRONMENT") or os.getenv("ENVIRONMENT")
    candidates: list[str] = []
    if env_name:
        candidates.append(f".env.{env_name.lower()}")
    candidates.extend([".env.development", ".env"])

    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None
