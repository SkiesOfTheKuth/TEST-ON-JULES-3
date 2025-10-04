# Calculator Gateway Service

FastAPI-based entrypoint that authenticates requests, enforces quotas, and forwards calculations to the safe evaluator microservice.

## Database migrations

The gateway uses Alembic to manage its PostgreSQL schema. Run migrations with:

```bash
poetry run alembic upgrade head
```

The initial migration provisions the `api_keys`, `request_audit`, and `quotas` tables along with supporting indexes and foreign-key constraints.

## Seed a default API key

For local development you can bootstrap a default API key by executing:

```bash
poetry run python -m app.scripts.seed_api_key
```

Override the defaults using command-line flags or environment variables:

```bash
poetry run python -m app.scripts.seed_api_key --api-key=my-key --owner="QA" --scopes="calculate,inspect"
```

Environment variables `GATEWAY_SEED_API_KEY`, `GATEWAY_SEED_API_KEY_OWNER`, and `GATEWAY_SEED_API_KEY_SCOPES` provide the same overrides. Pass `--force` to update an existing record while keeping the raw key the same.

## Redis namespaces and TTLs

Redis keys follow the pattern:

| Purpose | Key pattern | Default TTL |
| --- | --- | --- |
| API key rate limiting | `rate:{api_key_id}` | 60 seconds |
| IP limiter | `limiter:{ip}` | 60 seconds |
| Calculation result cache | `cache:{expression_hash}` | 5 minutes |

All TTL values are configurable through `GatewaySettings.redis` in `app/config.py`.
