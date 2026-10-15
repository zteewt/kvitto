"""Окружение Alembic.

Берёт URL из ``DATABASE_URL`` — тот же источник, что и приложение, поэтому
миграции и сервис всегда смотрят в одну базу.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Корень репозитория в sys.path: пакет kvitto должен импортироваться без установки.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kvitto.infrastructure.db import models  # noqa: F401
from kvitto.infrastructure.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Переопределяем URL только если он пришёл из окружения. Иначе уважаем
# значение, заданное вызывающим кодом (см. infrastructure/db/schema.py) —
# иначе миграции уедут в базу по умолчанию вместо тестовой.
_env_url = os.getenv("DATABASE_URL")
if _env_url:
    config.set_main_option("sqlalchemy.url", _env_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Миграции без подключения к БД — генерация SQL."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Миграции с подключением к БД."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # SQLite не умеет ALTER почти ничего — ограничиваем автогенерацию.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
