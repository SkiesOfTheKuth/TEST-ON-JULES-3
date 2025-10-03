"""WSGI entry point for the calculator service."""

from __future__ import annotations

from calculator_app import create_app

app = create_app()

if __name__ == "__main__":  # pragma: no cover - script entry point
    app.run(host="0.0.0.0", port=5000, debug=False)
