# Python FastAPI Single-Container Production Image
FROM python:3.12-slim
WORKDIR /app

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy backend dependencies pyproject.toml
COPY backend/pyproject.toml backend/uv.lock* ./backend/
WORKDIR /app/backend
RUN uv sync

# Copy backend code and pre-built static frontend
COPY backend/ /app/backend/

# Create DB volume directory
RUN mkdir -p /app/db

EXPOSE 8000
EXPOSE 8080

# Run uvicorn HTTPS server
CMD ["uv", "run", "python", "run_server.py"]
