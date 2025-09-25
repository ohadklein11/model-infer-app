FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:${PATH}"

# Install uv
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        curl ca-certificates \
        libgl1 \
        libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/* \
 && curl -LsSf https://astral.sh/uv/install.sh | sh

COPY yolo/pyproject.toml /app/pyproject.toml
COPY yolo/uv.lock /app/uv.lock
COPY shared /app/shared

RUN uv sync --no-dev && \
    cd /app/shared && uv build && \
    pip install --no-deps dist/*.whl

COPY yolo /app

EXPOSE 8093

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8093"]
