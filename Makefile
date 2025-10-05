PYTHON ?= python3
POETRY ?= poetry

.PHONY: bootstrap lint test run-gateway run-evaluator compose-up compose-down

bootstrap:
	$(POETRY) -C services/gateway install
	$(POETRY) -C services/safe_evaluator install

lint:
	$(POETRY) -C services/gateway run ruff check app ../safe_evaluator/app ../../libs

test:
	$(POETRY) -C services/safe_evaluator run pytest ../../tests

run-gateway:
	$(POETRY) -C services/gateway run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

run-evaluator:
	$(POETRY) -C services/safe_evaluator run python -m app.server

compose-up:
	docker compose -f docker-compose.phase1.yml up --build

compose-down:
	docker compose -f docker-compose.phase1.yml down

.PHONY: quick-check
quick-check:
	@python scripts/verify_observability.py

.PHONY: quick-tests
quick-tests:
	@poetry run pytest -q tests/metrics/test_metrics_endpoint.py tests/metrics/test_worker_signals.py
