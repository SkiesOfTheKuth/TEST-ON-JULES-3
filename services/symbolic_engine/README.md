# Symbolic Engine Service

The Symbolic Engine is a lightweight FastAPI microservice that evaluates SymPy
expressions inside a sandboxed subprocess. Responses are cached in Redis for
300 seconds and instrumented with Prometheus metrics.

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r services/symbolic_engine/requirements.txt
uvicorn services.symbolic_engine.app.main:app --reload --port 8080
```

## Running Tests

Tests require Redis and SymPy. Use the provided Compose stack:

```bash
docker compose -f docker-compose.test.yml up --build -d redis symbolic
pytest tests/symbolic_engine -q
```
