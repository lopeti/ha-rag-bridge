FROM python:3.12-slim

ENV POETRY_VERSION=1.8.3

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl tini && \
    pip install --no-cache-dir poetry==$POETRY_VERSION && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false && \
    poetry config installer.no-binary :none:

# 👇 Add this line before poetry install
COPY . .

# 👇 DEBUG: list files & folders
RUN ls -R /app && echo "===> ls done" && \
    find /app -type f -name '*.py' && echo "===> find done"

RUN poetry install --no-interaction --no-ansi --only main

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
