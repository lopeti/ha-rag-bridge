# 🐍 Base Python slim image
FROM busybox:1.36 as tini

FROM python:3.12-slim
COPY --from=tini /bin/tini /tini

# 📁 Set working directory
WORKDIR /app

# 🔧 Install system dependencies needed for building Python packages
RUN apt-get update --allow-releaseinfo-change && \
    apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl gnupg && \
    rm -rf /var/lib/apt/lists/*

# 🔧 Install a stable version of Poetry
ENV POETRY_VERSION=1.8.2
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# 📋 Disable virtualenvs (so dependencies are installed directly in container environment)
ENV POETRY_VIRTUALENVS_CREATE=false

# 📄 Copy dependency files and install Python dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root

# 📄 Copy application code
COPY . .
# install package so CLI is available
RUN poetry install --only-root

# 🚀 Run the FastAPI application with Uvicorn
ENTRYPOINT ["/tini","--"]
CMD ["sh", "-c", "ha-rag-bootstrap && uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-config docker/uvicorn_log.ini"]
