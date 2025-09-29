"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from app import app as flask_app


@pytest.fixture()
def client():
    """Flask test client fixture."""

    flask_app.config.update(
        TESTING=True,
        API_KEY="test-token",
        RATE_LIMIT="1000 per minute",
    )

    with flask_app.test_client() as client:
        yield client


@pytest.fixture()
def evaluator():
    """Safe evaluator fixture for convenience."""

    from safe_evaluator import SafeEvaluator

    return SafeEvaluator()

