.PHONY: format lint test typecheck security docker-build

format:
ruff check --select I --fix .
black .

lint:
ruff check .

typecheck:
mypy calculator_app

test:
pytest --cov

security:
pip-audit

docker-build:
docker build -t calculator-app:latest .
