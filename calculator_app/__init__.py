"""Calculator Flask application factory and extensions."""

from __future__ import annotations

import logging
import os
from http import HTTPStatus
from time import perf_counter
from typing import Any

from flask import Flask, Response, current_app, g, request

from .logging_utils import JsonFormatter
from .metrics import MetricsStore, _METRICS_CONTENT_TYPE
from .rate_limit import RateLimitExceeded, SimpleRateLimiter
from .routes import bp as calculator_blueprint
from .services.evaluator import SafeEvaluator


def _configure_logging(log_level: str) -> None:
    """Configure structured JSON logging for the application."""

    formatter = JsonFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def create_app(config_overrides: dict[str, Any] | None = None) -> Flask:
    """Application factory used by tests and production deployments."""

    log_level = os.getenv("LOG_LEVEL", "INFO")
    _configure_logging(log_level)

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    app.config.from_mapping(
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "change-me"),
        JSON_SORT_KEYS=False,
        API_KEY=os.getenv("CALCULATOR_API_KEY"),
        RATE_LIMIT=os.getenv("CALCULATOR_RATE_LIMIT", "60/minute"),
        EVALUATOR_MAX_EXPRESSION_LENGTH=int(
            os.getenv("CALCULATOR_MAX_EXPRESSION_LENGTH", "256")
        ),
        EVALUATOR_MAX_RUNTIME=float(os.getenv("CALCULATOR_MAX_RUNTIME_SECONDS", "0.1")),
        EVALUATOR_MAX_RESULT=float(
            os.getenv("CALCULATOR_MAX_RESULT_MAGNITUDE", "1e12")
        ),
        ALLOW_INSECURE_SECRET=os.getenv("CALCULATOR_ALLOW_INSECURE_SECRET", "false")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
    )

    if config_overrides:
        app.config.update(config_overrides)

    app.extensions["calculator_evaluator"] = SafeEvaluator(
        max_expression_length=app.config["EVALUATOR_MAX_EXPRESSION_LENGTH"],
        max_runtime_seconds=app.config["EVALUATOR_MAX_RUNTIME"],
        max_result_magnitude=app.config["EVALUATOR_MAX_RESULT"],
    )
    def _limit_provider() -> str | None:
        try:
            return current_app.config.get("RATE_LIMIT")
        except RuntimeError:  # no active app context
            return app.config.get("RATE_LIMIT")

    app.extensions["calculator_rate_limiter"] = SimpleRateLimiter(_limit_provider)
    metrics_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")
    app.extensions["calculator_metrics"] = MetricsStore(metrics_dir)

    if (
        not app.config.get("TESTING")
        and not app.config.get("ALLOW_INSECURE_SECRET")
        and app.config.get("SECRET_KEY") in {None, "", "change-me"}
    ):
        raise RuntimeError(
            "FLASK_SECRET_KEY must be set to a non-default value for secure deployments."
        )
    if app.config.get("SECRET_KEY") == "change-me":
        logging.getLogger(__name__).warning(
            "SECRET_KEY is using the default value; set FLASK_SECRET_KEY for production."
        )

    app.register_blueprint(calculator_blueprint)

    _register_request_hooks(app)

    _register_error_handlers(app)

    @app.get("/healthz")
    def health() -> tuple[dict[str, str], int]:  # pragma: no cover - trivial
        return {"status": "ok"}, HTTPStatus.OK

    @app.get("/readyz")
    def ready() -> tuple[dict[str, str], int]:
        evaluator: SafeEvaluator = app.extensions["calculator_evaluator"]
        try:
            evaluator.health_check()
        except RuntimeError:
            return {"status": "unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE
        return {"status": "ready"}, HTTPStatus.OK

    @app.get("/metrics")
    def metrics() -> Response:  # pragma: no cover - exercised via integration test
        metrics_store: MetricsStore = app.extensions["calculator_metrics"]
        payload = metrics_store.render()
        return Response(payload, content_type=_METRICS_CONTENT_TYPE)

    return app


def _register_request_hooks(app: Flask) -> None:
    """Attach request lifecycle hooks for observability and headers."""

    @app.before_request
    def _start_timer() -> None:  # pragma: no cover - simple assignment
        g.request_started_at = perf_counter()

    @app.after_request
    def _apply_security_headers(response):  # type: ignore[override]
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'",
        )

        logger = logging.getLogger(__name__)
        duration_ms = None
        started_at = g.pop("request_started_at", None)
        if started_at is not None:
            duration_ms = (perf_counter() - started_at) * 1000

        logger.info(
            "request",
            extra={
                "event": "http_request",
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "remote_addr": request.remote_addr,
                "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
            },
        )

        endpoint = request.url_rule.rule if request.url_rule else request.path
        metrics: MetricsStore = app.extensions["calculator_metrics"]
        metrics.record_request(request.method, endpoint, str(response.status_code))
        if duration_ms is not None:
            metrics.record_latency(request.method, endpoint, duration_ms / 1000)

        if request.endpoint == "static":
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

        return response


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(RateLimitExceeded)
    def _handle_rate_limit(exc: RateLimitExceeded):  # pragma: no cover - integration tested
        from flask import jsonify

        response = jsonify({"error": str(exc)})
        if exc.retry_after is not None:
            response.headers["Retry-After"] = f"{int(exc.retry_after)}"
        return response, HTTPStatus.TOO_MANY_REQUESTS


__all__ = ["create_app"]
