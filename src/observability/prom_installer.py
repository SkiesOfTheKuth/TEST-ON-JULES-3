"""Reusable Prometheus `/metrics` endpoint installer for ASGI-style apps."""

from __future__ import annotations

from typing import Any, Iterable

from fastapi import FastAPI  # type: ignore[attr-defined]
from prometheus_client import CollectorRegistry, REGISTRY, generate_latest

try:  # pragma: no cover - optional dependency bridge
    from fastapi.responses import Response  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - minimal fallback
    class Response:  # type: ignore[override]
        def __init__(self, content: bytes, media_type: str, headers: dict[str, str] | None = None) -> None:
            self.body = content
            self.media_type = media_type
            self.headers = headers or {}
            self.status_code = 200

        def __call__(self) -> "Response":  # pragma: no cover - compatibility shim
            return self

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
_FALLBACK_BODY = b"# HELP exporter_placeholder_info Exporter bootstrap placeholder\n" \
    b"# TYPE exporter_placeholder_info gauge\n" \
    b"# no_metrics_yet 1\n"

__all__ = ["install_prometheus_endpoint", "PROMETHEUS_CONTENT_TYPE"]


def _has_metrics(registry: CollectorRegistry) -> bool:
    """Return ``True`` if the registry contains at least one sample."""

    try:
        collectors: Iterable = registry.collect()  # type: ignore[assignment]
    except Exception:  # pragma: no cover - registry implementations may vary
        return False

    for metric in collectors:
        samples = getattr(metric, "samples", [])
        if samples:
            return True
    return False


def _route_exists(app: FastAPI, path: str) -> bool:
    router = getattr(app, "router", None)
    if router is not None:
        for route in getattr(router, "routes", []) or []:
            route_path = getattr(route, "path", getattr(route, "path_format", None))
            methods = getattr(route, "methods", None)
            if route_path == path and (methods is None or "GET" in methods):
                return True
    for route in getattr(app, "routes", []) or []:
        if isinstance(route, tuple):
            route_path = route[0]
            if route_path == path:
                return True
            continue
        route_path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if route_path == path and (methods is None or "GET" in methods):
            return True
    return False


def install_prometheus_endpoint(
    app: FastAPI,
    path: str = "/metrics",
    registry: CollectorRegistry | None = None,
) -> None:
    """Expose a Prometheus metrics endpoint if it has not already been registered."""

    if _route_exists(app, path):
        return

    registry = registry or REGISTRY

    async def _metrics_endpoint() -> Response:
        has_metrics = _has_metrics(registry)
        try:
            payload = generate_latest(registry)
        except Exception:  # pragma: no cover - defensive fallback
            payload = _FALLBACK_BODY
        else:
            if not has_metrics or not payload.strip():
                payload = _FALLBACK_BODY
        return Response(
            content=payload,
            media_type=PROMETHEUS_CONTENT_TYPE,
            headers={"Cache-Control": "no-store"},
        )

    router = getattr(app, "router", None)
    add_api_route = getattr(router, "add_api_route", None)
    if callable(add_api_route):
        add_api_route(path, _metrics_endpoint, methods=["GET"], include_in_schema=False)
    else:
        getter = getattr(app, "get", None)
        if getter is None:
            raise AttributeError("Application must expose a route registration helper")
        getter(path)(_metrics_endpoint)
