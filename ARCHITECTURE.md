# Architecture

```
+--------------+       +----------------------+       +---------------------+
|   Browser    | <---> | Flask App (Gunicorn) | <---> | SafeEvaluator Layer |
+--------------+       +----------------------+       +---------------------+
        |                         |                               |
        | HTTP / WebSocket        | Logging/metrics                | asteval sandbox with
        v                         v                               v
  calculator_app/static    JSON logs + `/metrics`        limited math operations
```

## Modules
- `calculator_app/__init__.py`: application factory, lifecycle hooks, config.
- `calculator_app/routes.py`: blueprint with UI + `/calculate` endpoint.
- `calculator_app/services/evaluator.py`: hardened expression sandbox.
- `calculator_app/operations.py`: curated math helper functions.
- `calculator_app/metrics.py`: Thread-safe metrics registry powering `/metrics` with optional multiprocess aggregation via `PROMETHEUS_MULTIPROC_DIR`.
- `calculator.py` & `gui_calculator.py`: CLI and Tkinter interfaces.

## Dependencies
- Flask 3.x
- asteval for controlled expression evaluation
- Custom in-process rate limiter (single-node) with recommendation to front with gateway/WAF
- Native JSON logging formatter (`calculator_app/logging_utils.py`)

## Configuration strategy
- Twelve-factor: environment variables only, sample `.env.example` provided.
- Runtime overrides via `create_app(config_overrides=dict(...))` for tests.
- Startup enforcement ensures `FLASK_SECRET_KEY` is non-default unless `CALCULATOR_ALLOW_INSECURE_SECRET` is explicitly enabled.

## Error handling policy
- 4xx errors for validation/auth failures; 5xx masked with generic message.
- JSON responses with deterministic schema for API clients.
- Uncaught exceptions logged with stack traces.

## Internationalization & timezones
- UTF-8 throughout, frontend uses `lang="en"` but content static.
- All timestamps emitted in UTC via logging formatter.
- Time-sensitive configs (rate limits, retention) expressed in ISO units.
