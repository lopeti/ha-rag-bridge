# 🐍 Alap Python slim image
FROM python:3.11-slim

# 📝 Munkakönyvtár
WORKDIR /app

# 🔧 Poetry telepítés + dependenciák
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-root

# 📄 Kód bemásolása
COPY . .

# 🚀 Indítás
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
