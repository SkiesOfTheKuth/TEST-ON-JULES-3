"""Flask entry-point for the calculator application."""

from __future__ import annotations

import hmac
import logging
import os
from http import HTTPStatus
from time import perf_counter

from flask import Flask, jsonify, render_template, request, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pythonjsonlogger import jsonlogger

from safe_evaluator import (
    ExpressionEvaluationError,
    ExpressionValidationError,
    SafeEvaluator,
)


def _configure_logging() -> None:
    formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


_configure_logging()

LOGGER = logging.getLogger(__name__)

app = Flask(__name__)
app.config.setdefault("JSON_SORT_KEYS", False)
app.config.setdefault("API_KEY", os.getenv("CALCULATOR_API_KEY"))
app.config.setdefault("RATE_LIMIT", os.getenv("CALCULATOR_RATE_LIMIT", "60/minute"))
app.config.setdefault(
    "RATELIMIT_STORAGE_URI",
    os.getenv("CALCULATOR_RATELIMIT_STORAGE_URI", "memory://"),
)
app.config.setdefault(
    "EVALUATOR_MAX_RUNTIME",
    float(os.getenv("CALCULATOR_MAX_RUNTIME_SECONDS", "0.1")),
)
app.config.setdefault(
    "EVALUATOR_MAX_RESULT",
    float(os.getenv("CALCULATOR_MAX_RESULT_MAGNITUDE", "1e12")),
)

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=app.config["RATELIMIT_STORAGE_URI"],
    default_limits=[],
)
limiter.init_app(app)

_SAFE_EVALUATOR = SafeEvaluator(
    max_runtime_seconds=app.config["EVALUATOR_MAX_RUNTIME"],
    max_result_magnitude=app.config["EVALUATOR_MAX_RESULT"],
)


def _is_authorized() -> bool:
    api_key = app.config.get("API_KEY")
    if not api_key:
        return True

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return False

    provided = header.removeprefix("Bearer ").strip()
    return hmac.compare_digest(provided, api_key)


@app.before_request
def _start_timer() -> None:
    g.request_started_at = perf_counter()


@app.after_request
def _apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self'",
    )

    start_time = g.pop("request_started_at", None)
    if start_time is not None:
        duration_ms = (perf_counter() - start_time) * 1000
    else:
        duration_ms = None

    LOGGER.info(
        "request",
        extra={
            "event": "http_request",
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
            "remote_addr": request.remote_addr,
        },
    )

    return response


@app.route("/")
def index():
    return render_template("index.html")


@limiter.limit(lambda: app.config["RATE_LIMIT"])
@app.route("/calculate", methods=["POST"])
def calculate():
    if not _is_authorized():
        LOGGER.warning(
            "Unauthorized request",
            extra={"event": "unauthorized", "remote_addr": request.remote_addr},
        )
        return jsonify({"error": "Unauthorized"}), HTTPStatus.UNAUTHORIZED

    payload = request.get_json(silent=True) or {}
    expression = payload.get("expression", "")

    try:
        result = _SAFE_EVALUATOR.evaluate(expression)
    except ExpressionValidationError as exc:
        LOGGER.warning("Validation error: %s", exc)
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
    except ExpressionEvaluationError as exc:
        LOGGER.warning("Evaluation error: %s", exc)
        return jsonify({"error": "Invalid expression"}), HTTPStatus.BAD_REQUEST
    except Exception:  # pragma: no cover - defensive logging
        LOGGER.exception("Unexpected error while evaluating expression")
        return jsonify({"error": "Internal server error"}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"result": result}), HTTPStatus.OK


@app.errorhandler(429)
def _handle_rate_limit(exc):  # pragma: no cover - exercised via integration tests
    response = jsonify({"error": "Rate limit exceeded"})
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response, HTTPStatus.TOO_MANY_REQUESTS


if __name__ == "__main__":  # pragma: no cover - script entry point
    app.run(host="0.0.0.0", port=5000, debug=False)
