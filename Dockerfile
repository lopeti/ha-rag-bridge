# --- Base stage ---
FROM python:3.12-slim AS base

ENV POETRY_VERSION=1.8.3

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl tini && \
    pip install --no-cache-dir poetry==$POETRY_VERSION && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false && \
    poetry config installer.no-binary :none:

# --- Production stage ---
FROM base AS prod
COPY . .
RUN poetry install --no-interaction --no-ansi --only main
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Development stage ---
FROM base AS dev
COPY . .
RUN poetry install --no-interaction --no-ansi --with dev

# Explicitly copy uvicorn_log.ini to the container
COPY docker/uvicorn_log.ini /app/docker/

# Debug: List contents of /app/docker
RUN echo "Contents of /app/docker:" && ls -R /app/docker
