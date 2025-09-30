# Calculator Service

A production-ready Flask service that evaluates arithmetic expressions via a hardened sandbox and exposes a responsive web UI, CLI, and Tkinter GUI.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
flask --app app run --debug
```

## Make commands

| Command        | Description                               |
| -------------- | ----------------------------------------- |
| `make lint`    | Run Ruff linting                          |
| `make typecheck` | Run mypy on application package         |
| `make test`    | Execute pytest suite with coverage        |
| `make format`  | Apply import sorting and Black formatting |
| `make security`| Run pip-audit dependency scan             |

## Environment variables

See [`.env.example`](.env.example) for the full list. The most important settings:

- `FLASK_SECRET_KEY` – required in production; do not use `change-me`.
- `CALCULATOR_API_KEY` – bearer token required for `/calculate`; omit to disable auth.
- `CALCULATOR_RATE_LIMIT` – limit per IP (e.g. `60/minute`).

## Interfaces

- **Web UI:** accessible calculator served at `/`.
- **HTTP API:** POST `/calculate` with `{ "expression": "1 + 2" }`.
- **CLI:** `python calculator.py`
- **GUI:** `python gui_calculator.py`

## Testing

```bash
pytest --cov
```

To run only HTTP API tests: `pytest tests/test_app.py`.

## Docker

```bash
docker build -t calculator-app:latest .
docker run --rm -p 5000:5000 --env-file .env calculator-app:latest
```

## Deployment

- Configure production-ready secrets and, for multi-node setups, enforce rate limiting at the edge (API gateway/WAF).
- Deploy behind TLS termination (e.g., ingress controller or reverse proxy).
- Forward structured JSON logs to centralized observability stack.
