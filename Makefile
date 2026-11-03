# ==============================================================================
# survey-data-pipeline automation Makefile
# ==============================================================================
.PHONY: help up down build run test lint format clean logs shell restart status generate-dirty

help:
	@echo "Available Makefile commands for survey-data-pipeline:"
	@echo "  make up              - Start MongoDB and PostgreSQL services in background"
	@echo "  make down            - Stop and remove all pipeline containers and networks"
	@echo "  make build           - Build the pipeline Docker image"
	@echo "  make run             - Run the full ETL pipeline inside Docker"
	@echo "  make run-local       - Run the pipeline locally with active Python environment"
	@echo "  make test            - Run pytest suite with coverage"
	@echo "  make lint            - Run ruff linter and black format check"
	@echo "  make format          - Auto-format code using ruff and black"
	@echo "  make clean           - Clean cache directories, pyc files, and test artifacts"
	@echo "  make logs            - Tail logs from all docker compose services"
	@echo "  make shell           - Open a bash shell in the pipeline container"
	@echo "  make generate-dirty  - Generate synthetic messy survey dataset"

up:
	docker compose up -d mongodb postgres

down:
	docker compose down -v

build:
	docker compose build pipeline

run:
	docker compose run --rm pipeline --source synthetic --batch-id auto

run-local:
	python -m survey_pipeline.run --source synthetic --batch-id auto

generate-dirty:
	python scripts/generate_dirty_survey.py --rows 50000 --output data/sample/survey_sample_dirty.csv

test:
	pytest tests/ -v --cov=survey_pipeline --cov-report=term-missing

lint:
	ruff check src/ tests/ scripts/
	black --check src/ tests/ scripts/

format:
	ruff check --fix src/ tests/ scripts/
	black src/ tests/ scripts/

logs:
	docker compose logs -f

shell:
	docker compose run --rm --entrypoint /bin/bash pipeline

restart: down up

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.py[cod]" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage coverage.xml dist build *.egg-info 2>/dev/null || true
