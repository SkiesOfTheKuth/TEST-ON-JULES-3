"""Notification-related Prometheus helpers."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, REGISTRY

__all__ = [
    "record_publish_success",
    "record_publish_failure",
    "ws_client_connected",
    "ws_client_disconnected",
    "record_ws_send_error",
]


def _get_or_register(metric_cls, name: str, documentation: str, *, labelnames=(), namespace: str | None = None):
    full_name = f"{namespace}_{name}" if namespace else name
    try:
        return metric_cls(name, documentation, labelnames=labelnames, namespace=namespace)
    except ValueError:
        existing = REGISTRY._names_to_collectors.get(full_name)  # type: ignore[attr-defined]
        if existing is None:
            raise
        return existing


_NOTIFICATION_SUCCESS = _get_or_register(
    Counter,
    "job_notifications_published_total",
    "Count of job update notifications published to Redis.",
)
_NOTIFICATION_FAILURE = _get_or_register(
    Counter,
    "job_notifications_failed_total",
    "Count of job update notifications that failed to publish.",
)
_WS_CLIENTS = _get_or_register(
    Gauge,
    "ws_clients",
    "Active WebSocket clients subscribed to job updates.",
    labelnames=("endpoint",),
)
_WS_SEND_ERRORS = _get_or_register(
    Counter,
    "ws_send_errors_total",
    "Total number of WebSocket send errors encountered.",
    labelnames=("endpoint",),
)


def record_publish_success() -> None:
    _NOTIFICATION_SUCCESS.inc()


def record_publish_failure() -> None:
    _NOTIFICATION_FAILURE.inc()


def ws_client_connected(endpoint: str) -> None:
    _WS_CLIENTS.labels(endpoint=endpoint).inc()


def ws_client_disconnected(endpoint: str) -> None:
    _WS_CLIENTS.labels(endpoint=endpoint).dec()


def record_ws_send_error(endpoint: str) -> None:
    _WS_SEND_ERRORS.labels(endpoint=endpoint).inc()
