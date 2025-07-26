# ─── BASE ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base
WORKDIR /workspace
RUN pip install poetry
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git \ 
      build-essential \
      curl \
      tini \
 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root

# ─── PRODUCTION ───────────────────────────────────────────────────────
FROM base AS prod
COPY . .
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ─── DEVELOPMENT ──────────────────────────────────────────────────────
FROM base AS dev
# telepítjük a dev-függőségeket is (feltéve, hogy a pyproject-ban benne vannak)
RUN poetry install --no-interaction --no-ansi --with dev
RUN pip install debugpy
COPY . .
CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
