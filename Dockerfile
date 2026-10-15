# syntax=docker/dockerfile:1

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Сначала зависимости: правка кода не пересобирает слой с pip.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY kvitto ./kvitto
COPY migrations ./migrations
COPY alembic.ini pyproject.toml README.md ./

# БД в тома, чтобы переживала пересборку контейнера.
ENV DATABASE_URL=sqlite:////data/kvitto.db
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

# Миграции выполняются при старте приложения (kvitto/infrastructure/db/schema.py).
CMD ["uvicorn", "kvitto.main:app", "--host", "0.0.0.0", "--port", "8000"]