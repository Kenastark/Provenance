# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY src ./src
COPY infra/alembic ./infra/alembic
RUN pip install --upgrade pip && pip install -e .

EXPOSE 8000

# Apply migrations, then serve the ASGI app. `prov db upgrade` is idempotent, so a
# restart is safe; the app is created via its factory.
CMD ["sh", "-c", "prov db upgrade && uvicorn provenance.api.app:create_app --factory --host 0.0.0.0 --port 8000"]
