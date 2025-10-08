PYTHON ?= python3
POETRY ?= poetry
COMPOSE ?= docker compose
COMPOSE_PHASE1_FILE ?= docker-compose.phase1.yml
COMPOSE_PHASE2_FILE ?= docker-compose.phase2.yml
HOST_POSTGRES_PORT ?= 35432
HOST_REDIS_PORT ?= 6379

.PHONY: bootstrap lint unit test integ migrations compose-phase1-up compose-phase1-down compose-phase2-up compose-phase2-down integration load-test ci-validate

bootstrap:
	$(POETRY) -C services/gateway install --with dev
	$(POETRY) -C services/safe_evaluator install --with dev

lint:
	$(POETRY) -C services/gateway run ruff check app
	$(POETRY) -C services/safe_evaluator run ruff check app

unit:
	$(POETRY) -C services/gateway run pytest tests --maxfail=1 -m "not integration" --cov=app --cov-report=xml --cov-report=term-missing
	$(POETRY) -C services/safe_evaluator run pytest ../../tests --maxfail=1 -m "not integration"

test: lint unit

migrations:
	$(POETRY) -C services/gateway run alembic upgrade head

compose-phase1-up:
	$(COMPOSE) -f $(COMPOSE_PHASE1_FILE) up --build

compose-phase1-down:
	$(COMPOSE) -f $(COMPOSE_PHASE1_FILE) down --remove-orphans

compose-phase2-up:
	$(COMPOSE) -f $(COMPOSE_PHASE2_FILE) up --build -d

compose-phase2-down:
	$(COMPOSE) -f $(COMPOSE_PHASE2_FILE) down --remove-orphans -v

integration:
	@bash -c 'set -euo pipefail; \
	DB_URL="postgresql+asyncpg://calculator:calculator@localhost:$(HOST_POSTGRES_PORT)/calculator"; \
	TEST_KEY="${TEST_GATEWAY_API_KEY:-test-key-automation}"; \
	$(COMPOSE) -f $(COMPOSE_PHASE2_FILE) up --build -d postgres redis safe-evaluator symbolic-engine worker-standard worker-priority worker-gpu worker-symbolic tempo loki promtail prometheus grafana; \
	trap "$(COMPOSE) -f $(COMPOSE_PHASE2_FILE) down --remove-orphans -v" EXIT; \
	$(COMPOSE) -f $(COMPOSE_PHASE2_FILE) run --rm gateway alembic upgrade head; \
	$(COMPOSE) -f $(COMPOSE_PHASE2_FILE) up --build -d gateway; \
	sleep 5; \
	$(COMPOSE) -f $(COMPOSE_PHASE2_FILE) exec gateway python -m app.scripts.seed_api_key --api-key "$$TEST_KEY" --owner "Integration Test" --scopes calculate --force; \
	GATEWAY_REDIS__URL="redis://localhost:$(HOST_REDIS_PORT)/0" TEST_GATEWAY_API_KEY="$$TEST_KEY" GATEWAY_DATABASE__URL="$$DB_URL" $(POETRY) -C services/gateway run pytest services/gateway/tests/integration -m integration --maxfail=1;'

load-test:
	$(POETRY) -C services/gateway run locust -f tests/load/locustfile.py --headless --users=$${USERS:-10} --spawn-rate=$${SPAWN_RATE:-5} --run-time=$${RUN_TIME:-2m} --host=$${HOST:-http://localhost:8080} --api-key=$${API_KEY:?API_KEY env var required}

ci-validate: lint unit integration
