"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from calculator_app import create_app


@pytest.fixture()
def app():
    """Application instance configured for tests."""

    app = create_app(
        {
            "TESTING": True,
            "API_KEY": "test-token",
            "RATE_LIMIT": "1000 per minute",
        }
    )
    yield app


@pytest.fixture()
def client(app):
    """Flask test client fixture."""

    return app.test_client()


@pytest.fixture()
def evaluator():
    """Safe evaluator fixture for convenience."""

    from calculator_app.services.evaluator import SafeEvaluator

    return SafeEvaluator()

