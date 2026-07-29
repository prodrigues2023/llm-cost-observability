.PHONY: up down test lint type-check console

up:
	docker compose up -d --build
	@echo "waiting for the console..."
	@until curl -sf http://localhost:8000/api/summary > /dev/null; do sleep 1; done
	@echo "console: http://localhost:8000"

down:
	docker compose down

# Runs the console locally without Docker -- stubbed model, synthetic
# traffic, SQLite in-memory by default (COST_DB_PATH unset).
console:
	pip install -r requirements.txt > /dev/null
	python -m uvicorn console.app:app --host 0.0.0.0 --port 8000

test:
	pip install -r requirements.txt > /dev/null
	pytest tests/ -q

lint:
	ruff check costkit console tests

type-check:
	mypy costkit --ignore-missing-imports
