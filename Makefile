.PHONY: up down test lint type-check console validate drills

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
	ruff check costkit console tests eval

type-check:
	mypy costkit --ignore-missing-imports

# Milestone 4: regenerates docs/validation/*.md. The pass/fail claim
# itself is enforced by `make test`'s tests/test_validation_drills.py;
# this just re-runs and republishes the reports.
drills:
	pip install -r requirements.txt > /dev/null
	python -m eval.run_cost_regression_drill
	python -m eval.run_retry_storm_drill
	python -m eval.run_context_bloat_drill
	python -m eval.run_attribution_reconciliation

validate: test lint type-check drills
