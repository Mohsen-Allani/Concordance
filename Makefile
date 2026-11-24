.PHONY: help install lint format-check test test-pg migrate serve up down clean

PYTHON ?= python

help:  ## List available commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install:  ## Install the project with development tools
	$(PYTHON) -m pip install -e ".[dev]"

lint:  ## Static analysis (ruff)
	ruff check .

test:  ## Run the test suite (SQLite, no external service needed)
	pytest

test-pg:  ## Also run migration tests (needs TEST_POSTGRES_URL)
	pytest tests/test_migrations.py -v

migrate:  ## Apply database migrations
	alembic upgrade head

serve:  ## Start the web application with auto-reload
	concordance serve --reload

up:  ## Start the application and PostgreSQL with Docker Compose
	docker compose up --build

down:  ## Stop Docker Compose services
	docker compose down

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
