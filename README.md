# Calculator Service

A production-ready Flask service that evaluates arithmetic expressions via a hardened sandbox and exposes a responsive web UI, CLI, and Tkinter GUI.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
# Update FLASK_SECRET_KEY before running locally or set CALCULATOR_ALLOW_INSECURE_SECRET=true
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

- `FLASK_SECRET_KEY` – required in production; startup fails if unset or `change-me`.
- `CALCULATOR_ALLOW_INSECURE_SECRET` – set to `true` only for local experiments.
- `CALCULATOR_API_KEY` – bearer token required for `/calculate`; omit to disable auth.
- `CALCULATOR_RATE_LIMIT` – limit per IP (e.g. `60/minute`).

## Interfaces

- **Web UI:** accessible calculator served at `/`.
- **HTTP API:** POST `/calculate` with `{ "expression": "1 + 2" }`.
- **CLI:** `python calculator.py` for interactive mode or `python calculator.py --expression "1 + 2"` for single-shot.
- **GUI:** `python gui_calculator.py` to launch Tkinter UI or `python gui_calculator.py --smoke-test "1 + 2"` in headless automation.

## Observability & health

- **Health probes:** `GET /healthz` (liveness) and `GET /readyz` (readiness, runs a sandbox self-test).
- **Metrics:** `GET /metrics` emits Prometheus-compatible counters/histograms (requests, latency, evaluator outcomes) with optional multi-process aggregation via `PROMETHEUS_MULTIPROC_DIR`.
- **Logs:** Structured JSON to stdout with latency, status, and remote address for each request.

## Testing

```bash
pytest --cov
```

Targeted suites:

- HTTP API: `pytest tests/test_app.py`
- CLI smoke: `pytest tests/test_cli.py`
- GUI smoke: `pytest tests/test_gui.py`
- Observability: `pytest tests/test_observability.py`

## Docker

```bash
docker build -t calculator-app:latest .
docker run --rm -p 5000:5000 --env-file .env calculator-app:latest
```

## Deployment

- Configure production-ready secrets and, for multi-node setups, enforce rate limiting at the edge (API gateway/WAF).
- Deploy behind TLS termination (e.g., ingress controller or reverse proxy).
- Restrict `/metrics` scraping to trusted networks or mTLS-enabled collectors.
- Static assets ship with `Cache-Control: public, max-age=31536000, immutable`; bust caches by revving filenames on release.
- Forward structured JSON logs to centralized observability stack.
