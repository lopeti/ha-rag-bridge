FROM python:3.12-slim

WORKDIR /workspace

RUN pip install poetry

COPY pyproject.toml poetry.lock* /workspace/
RUN poetry install --no-root

COPY . /workspace

CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
