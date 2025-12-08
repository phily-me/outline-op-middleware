FROM python:3.14-slim-trixie

# Install system dependencies for healthchecks
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable uv cache
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies in a cached layer
# This layer will only rebuild if pyproject.toml or uv.lock changes
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Copy application code
COPY . .

# Install the project itself (fast since dependencies are cached)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.outline_op_middleware.main:app", "--host", "0.0.0.0", "--port", "8000"]
