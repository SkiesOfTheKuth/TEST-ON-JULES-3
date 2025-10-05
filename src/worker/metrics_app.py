"""FastAPI application exposing worker metrics for sidecar deployments.

Usage examples
--------------
* Development::

    uvicorn worker.metrics_app:app --port 9109

* Container sidecar::

    uvicorn worker.metrics_app:app --host 0.0.0.0 --port 9109
"""

from __future__ import annotations

from fastapi import FastAPI

from src.observability.prom_installer import install_prometheus_endpoint

__all__ = ["app", "create_app"]


def create_app(*, path: str = "/metrics") -> FastAPI:
    """Create a FastAPI application that serves Prometheus metrics."""

    app = FastAPI(title="Worker Metrics")
    install_prometheus_endpoint(app, path=path)
    return app


app = create_app()
