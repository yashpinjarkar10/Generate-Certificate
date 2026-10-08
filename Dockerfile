# Base Python image
FROM python:3.13-slim

# Install system dependencies (libatomic1 is required by Node.js for Prisma CLI)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libatomic1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv directly from official binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Enable bytecode compilation, configure virtualenv path
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy dependency definition files
COPY pyproject.toml uv.lock ./
COPY prisma/ ./prisma/

# Install dependencies using uv and generate Prisma client
RUN uv sync --frozen --no-dev && \
    uv run prisma generate

# Copy project application source code and static frontend
COPY app/ ./app/
COPY frontend/ ./frontend/

# Expose default port
EXPOSE 8000

# Run with dynamic PORT and ROLE support (ROLE=worker runs the background worker, otherwise runs FastAPI API)
CMD ["sh", "-c", "if [ \"$ROLE\" = \"worker\" ]; then exec uvicorn app.queue.run_worker:app --host 0.0.0.0 --port ${PORT:-8000}; else exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
