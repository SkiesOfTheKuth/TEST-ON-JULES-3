"""HTTP routes for the calculator application."""

from __future__ import annotations

import hmac
import logging
from http import HTTPStatus

from flask import Blueprint, current_app, jsonify, render_template, request

from .rate_limit import rate_limited
from .services.evaluator import (
    ExpressionEvaluationError,
    ExpressionValidationError,
)

LOGGER = logging.getLogger(__name__)

bp = Blueprint("calculator", __name__)


def _is_authorized() -> bool:
    api_key = current_app.config.get("API_KEY")
    if not api_key:
        return True

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return False

    provided = header.removeprefix("Bearer ").strip()
    return hmac.compare_digest(provided, api_key)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.post("/calculate")
@rate_limited
def calculate():
    if not _is_authorized():
        LOGGER.warning(
            "Unauthorized request",
            extra={"event": "unauthorized", "remote_addr": request.remote_addr},
        )
        return jsonify({"error": "Unauthorized"}), HTTPStatus.UNAUTHORIZED

    payload = request.get_json(silent=True) or {}
    expression = payload.get("expression", "")

    evaluator = current_app.extensions["calculator_evaluator"]

    try:
        result = evaluator.evaluate(expression)
    except ExpressionValidationError as exc:
        LOGGER.warning("Validation error: %s", exc)
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
    except ExpressionEvaluationError as exc:
        LOGGER.warning("Evaluation error: %s", exc)
        return jsonify({"error": "Invalid expression"}), HTTPStatus.BAD_REQUEST
    except Exception:  # pragma: no cover - defensive logging
        LOGGER.exception("Unexpected error while evaluating expression")
        return (
            jsonify({"error": "Internal server error"}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    return jsonify({"result": result}), HTTPStatus.OK


@bp.app_errorhandler(429)
def _handle_rate_limit(exc):  # pragma: no cover - exercised in tests
    response = jsonify({"error": "Rate limit exceeded"})
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response, HTTPStatus.TOO_MANY_REQUESTS
