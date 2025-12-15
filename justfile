# Justfile for outline-op-middleware
# Python FastAPI middleware for OpenProject and Outline integration

# Auto-detect deploy-kit invocation
_deploy_kit := if path_exists("deploy-kit/pyproject.toml") == "true" { "uvx --from ./deploy-kit deploy-kit" } else { "deploy-kit" }
_dev_port := "8002"

[private]
default:
  @just --list

# Deploy via docker-compose (SSH)
[group('deploy')]
up-compose target="":
    {{_deploy_kit}} up --compose {{target}}

# Deploy via Portainer API (pass URL as argument)
[group('deploy')]
up-portainer url="":
    {{_deploy_kit}} up --portainer {{url}}

# Teardown from remote server (compose backend)
[group('deploy')]
down-compose target="":
    {{_deploy_kit}} down --compose {{target}}

# Teardown from Portainer
[group('deploy')]
down-portainer url="":
    {{_deploy_kit}} down --portainer {{url}}


# SOPS helpers (use sops CLI directly)
[group('secrets')]
encrypt-secrets:
    sops --input-type dotenv --output-type dotenv -e .env > .env.sops
    @echo "Encrypted .env -> .env.sops"

[group('secrets')]
decrypt-secrets:
    sops --input-type dotenv --output-type dotenv -d .env.sops > .env
    @echo "Decrypted .env.sops -> .env (don't commit!)"

[group('secrets')]
edit-secrets:
    sops --input-type dotenv --output-type dotenv .env.sops


# Setup virtual environment and install dependencies
[group('development')]
setup:
    uv sync

# Run development server with auto-reload
[group('development')]
run:
    uv run uvicorn src.outline_op_middleware.main:app --host 0.0.0.0 --port {{_dev_port}} --reload

[group('development')]
run-docker:
    docker compose up --build

# Format and lint code
[group('development')]
lint:
    uv run ruff check --fix .
    uv run ruff format .

# Run tests with pytest
[group('testing')]
test:
    uv run pytest tests/ -v

# Run tests with coverage reporting
[group('testing')]
test-cov:
    uv run pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
