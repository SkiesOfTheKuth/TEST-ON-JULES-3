"""Flask entry-point for the calculator application."""

from __future__ import annotations

import logging
from http import HTTPStatus

from flask import Flask, jsonify, render_template, request

from safe_evaluator import (
    ExpressionEvaluationError,
    ExpressionValidationError,
    SafeEvaluator,
)


LOGGER = logging.getLogger(__name__)

app = Flask(__name__)
app.config.setdefault("JSON_SORT_KEYS", False)

_SAFE_EVALUATOR = SafeEvaluator()


@app.after_request
def _apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
    )
    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/calculate", methods=["POST"])
def calculate():
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


if __name__ == "__main__":  # pragma: no cover - script entry point
    app.run(host="0.0.0.0", port=5000, debug=False)
