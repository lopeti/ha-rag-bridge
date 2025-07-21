
# Stage 0 - download tini
FROM busybox:1.36 AS tini_download
ADD https://github.com/krallin/tini/releases/download/v0.19.0/tini-static /tini
RUN chmod +x /tini

# Stage 1 - application image
FROM python:3.12-slim

# rendszer csomagok + Rust
RUN apt-get update --allow-releaseinfo-change && \
    apt-get install -y --no-install-recommends \
        build-essential rustc cargo curl gnupg && \
    rm -rf /var/lib/apt/lists/*

# tini init wrapper
COPY --from=tini_download /tini /bin/tini

# set workdir
WORKDIR /app

# --- Poetry install ---
ENV POETRY_VERSION=1.8.3
RUN pip install --no-cache-dir poetry==$POETRY_VERSION && \
    poetry config virtualenvs.create false     \
 && poetry config installer.no-binary :none:   \
 && poetry install --no-interaction --no-ansi --only main
ENV PATH="/usr/local/bin:$PATH"

# install dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

# copy application
COPY . .

ENTRYPOINT ["/bin/tini","--"]
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
