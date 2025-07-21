# 🐍 Base image
FROM python:3.12-slim

# 📦 Poetry version
ENV POETRY_VERSION=1.8.3

# Install system dependencies, tini, and Poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl tini && \
    pip install --no-cache-dir poetry==$POETRY_VERSION && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy only dependency files first (for better build caching)
COPY pyproject.toml poetry.lock* ./

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    poetry config installer.no-binary :none: && \
    poetry install --no-interaction --no-ansi --only main

# Now copy the rest of the source code
COPY . .

# Use tini as PID 1 for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command: run FastAPI with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
