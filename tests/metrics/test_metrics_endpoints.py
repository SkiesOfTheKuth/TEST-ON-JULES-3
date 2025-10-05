import asyncio
import inspect

from fastapi import FastAPI

from src.gateway.instrumentation import expose_gateway_metrics, get_gateway_metrics
from src.worker.instrumentation import create_worker_metrics_app, get_worker_metrics


def _get_response_text(app: FastAPI, path: str = "/metrics") -> str:
    for route_path, handler in getattr(app, "routes", []):
        if route_path == path:
            result = handler()
            if inspect.isawaitable(result):
                response = asyncio.run(result)
            else:
                response = result
            assert response.status_code == 200
            body = getattr(response, "body", b"")
            if isinstance(body, bytes):
                return body.decode("utf-8")
            return str(body)
    raise AssertionError(f"No route registered for {path}")


def test_gateway_metrics_endpoint_exposes_registry() -> None:
    app = FastAPI()
    expose_gateway_metrics(app)

    metrics = get_gateway_metrics(namespace="gateway_test")
    metrics.jobs_enqueued_total.labels(queue="calculator").inc()

    body = _get_response_text(app)
    assert "gateway_test_jobs_enqueued_total" in body


def test_worker_metrics_app_exposes_metrics() -> None:
    app = create_worker_metrics_app(path="/metrics")

    metrics = get_worker_metrics(namespace="worker_test")
    metrics.jobs_failed.labels(queue="calculator", task="worker.task").inc()

    body = _get_response_text(app)
    assert "worker_test_jobs_failed" in body


def test_metrics_endpoint_registration_is_idempotent() -> None:
    app = FastAPI()
    expose_gateway_metrics(app)
    expose_gateway_metrics(app)

    body = _get_response_text(app)
    assert "# TYPE" in body
