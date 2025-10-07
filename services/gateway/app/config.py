"""Configuration for the gateway service."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
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


class SymbolicEngineSettings(BaseModel):
    base_url: str = "http://symbolic-engine:8100"
    request_timeout_seconds: float = 10.0
    cache_namespace: str = "symbolic"
    cache_ttl_seconds: int = 3600
    verification_enabled: bool = True
    verification_timeout_ms: int = 250
    verification_samples: int = 1



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
    heavy_queue_name: str = "calculator-jobs-heavy"
    gpu_queue_name: str = "calculator-jobs-gpu"
    symbolic_queue_name: str = "calculator-jobs-symbolic"
    cache_namespace: str = "jobs"
    rate_limit_requests: int = 5
    rate_limit_window_seconds: int = 1
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0
    rate_namespace: str = "job_rate"
    notification_namespace: str = "job_events"
    policy_cache_namespace: str = "policy"
    policy_cache_ttl_seconds: int = 300
    default_max_runtime_ms: int = 30000
    heavy_expression_keywords: list[str] = Field(
        default_factory=lambda: [
            "integrate",
            "derivative",
            "limit",
            "matrix",
            "det",
            "fft",
            "product(",
            "summation",
            "eigen",
            "laplace",
        ]
    )
    heavy_tags: list[str] = Field(default_factory=lambda: ["heavy", "batch", "long-running"])
    gpu_tags: list[str] = Field(default_factory=lambda: ["gpu", "cuda", "accelerate"])
    symbolic_tags: list[str] = Field(default_factory=lambda: ["symbolic", "sympy"])




class AutoscaleSettings(BaseModel):
    min_workers: int = 1
    max_workers: int = 20
    scale_up_step: int = 2
    scale_down_step: int = 1
    scale_up_queue_threshold: int = 75
    scale_down_queue_threshold: int = 15
    target_queue_wait_p95_seconds: float = 5.0
    target_cpu_percent: float = 85.0
    cooldown_seconds: int = 180
    drain_timeout_seconds: int = 30


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    redis: RedisSettings = RedisSettings()
    database: DatabaseSettings = DatabaseSettings()
    evaluator: EvaluatorSettings = EvaluatorSettings()
    observability: ObservabilitySettings = ObservabilitySettings()
    symbolic: SymbolicEngineSettings = SymbolicEngineSettings()
    quota: QuotaSettings = QuotaSettings()
    job: JobSettings = JobSettings()
    autoscale: AutoscaleSettings = AutoscaleSettings()
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

