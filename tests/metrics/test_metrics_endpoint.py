import asyncio
import inspect

from fastapi import FastAPI
from prometheus_client import CollectorRegistry

from src.observability.prom_installer import (
    PROMETHEUS_CONTENT_TYPE,
    install_prometheus_endpoint,
)


def _get_metrics_response(app: FastAPI, path: str = "/metrics"):
    routes = list(getattr(app, "routes", []) or [])
    if not routes:
        router = getattr(app, "router", None)
        routes = list(getattr(router, "routes", []) or []) if router is not None else []

    for route in routes:
        handler = None
        if isinstance(route, tuple):
            route_path, handler = route[0], route[1]
        else:
            route_path = getattr(route, "path", getattr(route, "path_format", None))
            handler = getattr(route, "endpoint", None) or getattr(route, "app", None)
        if route_path == path and handler is not None:
            result = handler()
            if inspect.isawaitable(result):
                return asyncio.run(result)
            return result
    raise AssertionError(f"No route registered for {path}")


def _route_count(app: FastAPI, path: str) -> int:
    count = 0
    for route in getattr(app, "routes", []) or []:
        if isinstance(route, tuple) and route[0] == path:
            count += 1
    router = getattr(app, "router", None)
    if router is not None:
        for route in getattr(router, "routes", []) or []:
            if getattr(route, "path", getattr(route, "path_format", None)) == path:
                count += 1
    return count


def test_install_prometheus_endpoint_is_idempotent_and_serves_fallback() -> None:
    app = FastAPI()
    registry = CollectorRegistry()

    install_prometheus_endpoint(app, registry=registry)
    install_prometheus_endpoint(app, registry=registry)

    response = _get_metrics_response(app)

    assert getattr(response, "status_code", 200) == 200
    media_type = getattr(response, "media_type", None)
    assert media_type == PROMETHEUS_CONTENT_TYPE

    body_lines = (getattr(response, "body", b"") or b"").decode("utf-8").splitlines()
    assert body_lines[0].startswith("# HELP")
    assert body_lines[1].startswith("# TYPE")
    assert "exporter_placeholder_info 1" in "\n".join(body_lines)

    assert _route_count(app, "/metrics") == 1


def test_install_prometheus_endpoint_with_existing_metrics() -> None:
    app = FastAPI()
    install_prometheus_endpoint(app)

    response = _get_metrics_response(app)

    assert getattr(response, "media_type", None) == PROMETHEUS_CONTENT_TYPE
    body_text = (getattr(response, "body", b"") or b"").decode("utf-8")
    assert "# HELP" in body_text
    assert "# TYPE" in body_text
