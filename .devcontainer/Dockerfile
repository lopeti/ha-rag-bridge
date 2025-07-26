# ─── BASE ─────────────────────────────────────────────────────────────
FROM python:3.13-slim AS base

ENV POETRY_VERSION=1.8.3

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl tini git && \
    pip install --no-cache-dir poetry==$POETRY_VERSION && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false && \
    poetry config installer.no-binary :none:

# ─── PRODUCTION ───────────────────────────────────────────────────────
FROM base AS prod
COPY . .
RUN poetry install --no-interaction --no-ansi --only main
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ─── DEVELOPMENT ──────────────────────────────────────────────────────
FROM base AS dev
COPY . .
RUN poetry install --no-interaction --no-ansi --with dev && \
    pip install debugpy
CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
