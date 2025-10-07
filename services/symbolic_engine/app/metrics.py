"""Prometheus metrics for the Symbolic Engine."""

from prometheus_client import Counter, Histogram

reqs = Counter(
    "sym_engine_requests_total",
    "Total requests served by the symbolic engine.",
    labelnames=("endpoint", "ok"),
)

lat = Histogram(
    "sym_engine_latency_seconds",
    "Request latency observed by the symbolic engine.",
    labelnames=("endpoint",),
)

cache_hits = Counter(
    "sym_engine_cache_hits_total",
    "Cache hits served by the symbolic engine.",
    labelnames=("endpoint",),
)

__all__ = ["reqs", "lat", "cache_hits"]
