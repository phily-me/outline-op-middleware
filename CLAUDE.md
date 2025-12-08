# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based middleware service that integrates OpenProject with Outline. When a work package in OpenProject has a custom field "KB anfordern" (KB request) set to true, this service automatically creates a knowledge base document in Outline using a template, then updates the OpenProject work package with the document URL.

## Architecture

**Main Application**: `src/outline_op_middleware/main.py`
- Single-file FastAPI application with webhook endpoint
- Uses async/await with httpx for HTTP requests
- Environment validation at startup via lifespan context manager
- Background task processing for webhook handling

**Workflow**:
1. OpenProject sends webhook to `/webhook` endpoint when work package is updated
2. Webhook signature is verified using HMAC SHA256
3. If "KB anfordern" custom field is true and no KB link exists, process in background
4. Fetch template from Outline, replace placeholders with work package data
5. Create new document in Outline
6. Update OpenProject work package with document URL and reset "KB anfordern" flag

## Development Commands

This project uses [just](https://github.com/casey/just) for task automation. Install just and run:

**Setup and install dependencies**:
```bash
just setup
```

**Run development server**:
```bash
just run
```

**Run tests**:
```bash
just test           # Run pytest tests
just test-cov       # Run tests with coverage reporting
```

**Lint and format code**:
```bash
just lint
```

**Build deployment package**:
```bash
just deploy <subdomain>
```

**Run in Docker**:
```bash
docker compose up --build
```

**Direct commands** (without just):
```bash
uv sync                           # Install dependencies
uv run uvicorn src.outline_op_middleware.main:app --host 0.0.0.0 --port 8000 --reload  # Run dev server
uv run pytest tests/ -v           # Run tests
```

## Environment Configuration

Copy `.env.example` to `.env` and configure:

**OpenProject**:
- `OP_BASE_URL`: OpenProject instance URL
- `OP_API_KEY`: API key for authentication
- `OP_WEBHOOK_SECRET`: Secret for webhook signature verification
- `OP_CF_KB_REQUEST`: Custom field ID for boolean "KB anfordern"
- `OP_CF_KB_LINK`: Custom field ID for text "KB Link"

**Outline**:
- `OUTLINE_BASE_URL`: Outline instance URL
- `OUTLINE_API_KEY`: Bearer token for API authentication
- `OUTLINE_COLLECTION_ID`: UUID of collection where documents are created
- `OUTLINE_TEMPLATE_ID`: UUID of template document

All environment variables are required and validated at startup.

## Template Placeholders

When creating Outline documents, these placeholders in the template are replaced:
- `{{WP_ID}}`: Work package ID
- `{{WP_SUBJECT}}`: Work package title
- `{{WP_DESCRIPTION}}`: Work package description (raw text)
- `{{WP_URL}}`: Full URL to work package

## OpenProject Webhook Configuration

Configure webhook in OpenProject to send POST requests to `/webhook` endpoint:
- Event: `work_package:updated`
- Include signature using `OP_WEBHOOK_SECRET`
- Header: `X-OP-Signature` with HMAC SHA256 hex digest

## Python Version

Requires Python 3.13+ (specified in pyproject.toml and Dockerfile uses 3.14-slim)
