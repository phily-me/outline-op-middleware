# Justfile for outline-op-middleware
# Python FastAPI middleware for OpenProject and Outline integration

port := "8001"

[private]
default:
  @just --list

# Setup virtual environment and install dependencies
setup:
    uv sync

# Run development server with auto-reload
run:
    uv run uvicorn src.outline_op_middleware.main:app --host 0.0.0.0 --port {{port}} --reload

run-docker:
    docker compose up --build

# Format and lint code
lint:
    uv run ruff check --fix .
    uv run ruff format .

# Run tests with pytest
test:
    uv run pytest tests/ -v

# Run tests with coverage reporting
test-cov:
    uv run pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

# Build Docker image and deploy to target server
deploy target:
    ./scripts/deploy.sh {{target}}
