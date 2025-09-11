FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Install uv (package/deps manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Copy project files needed for dependency resolution
COPY pyproject.toml /app/
COPY uv.lock /app/

# Install dependencies from pyproject/lockfile
RUN uv sync --frozen --no-dev

# Copy frontend source
COPY apps/frontend /app/frontend

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
