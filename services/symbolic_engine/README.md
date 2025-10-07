# Symbolic Engine Service

The Symbolic Engine is a FastAPI microservice that wraps SymPy-powered operations behind a
sandboxed execution boundary. It provides REST endpoints for algebraic simplification,
differentiation, integration, solving, series expansion, and code generation.

## Local Development

```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8082
```

## Running Tests

```bash
poetry run pytest
```
