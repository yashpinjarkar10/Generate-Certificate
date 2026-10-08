# Base Python image
FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv directly from official binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Enable bytecode compilation and set Python path
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1

# Copy dependency definition files
COPY pyproject.toml uv.lock ./
COPY prisma/ ./prisma/

# Install dependencies using uv and generate Prisma client
RUN uv sync --frozen --no-dev && \
    uv run prisma generate

# Copy project source code
COPY app/ ./app/
COPY main.py ./

# Expose FastAPI default port
EXPOSE 8000

# Default command (overridden in docker-compose)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
