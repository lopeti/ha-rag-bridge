# Stage 0 - download tini
FROM busybox:1.36 AS tini_download
ADD https://github.com/krallin/tini/releases/download/v0.19.0/tini-static /tini
RUN chmod +x /tini

# Stage 1 - application image
FROM python:3.12-slim

# system packages
RUN apt-get update --allow-releaseinfo-change && \
    apt-get install -y --no-install-recommends \
        build-essential rustc cargo cmake && \
    rm -rf /var/lib/apt/lists/*

# tini init wrapper
COPY --from=tini_download /tini /bin/tini

# set workdir
WORKDIR /app

# install poetry
ENV POETRY_VERSION=1.8.2
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# disable virtualenv creation
ENV POETRY_VIRTUALENVS_CREATE=false

# install dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root

# copy application
COPY . .
RUN poetry install --only-root

ENTRYPOINT ["/bin/tini","--"]
CMD ["sh", "-c", "ha-rag-bootstrap && uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-config docker/uvicorn_log.ini"]
