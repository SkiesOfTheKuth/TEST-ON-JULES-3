PYTHON ?= python3

.PHONY: bootstrap lint test run-gateway run-evaluator compose-up compose-down

bootstrap:
	$(PYTHON) -m pip install -e libs/calculator_logic
	$(PYTHON) -m pip install -e libs/calculator_core
	$(PYTHON) -m pip install -e services/gateway
	$(PYTHON) -m pip install -e services/safe_evaluator

lint:
	ruff check .

test:
	pytest

run-gateway:
	uvicorn services.gateway.app.main:app --host 0.0.0.0 --port 8080 --reload

run-evaluator:
	$(PYTHON) -m services.safe_evaluator.app.server

compose-up:
	docker compose -f docker-compose.phase1.yml up --build

compose-down:
	docker compose -f docker-compose.phase1.yml down
