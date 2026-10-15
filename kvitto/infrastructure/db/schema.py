"""Подготовка схемы при старте.

Два пути, но только один источник правды:

* Alembic установлен — выполняется ``upgrade head``;
* Alembic не установлен (минимальное окружение) — ``create_all()``.

Раньше схему могли создать два способа сразу, и тогда ``alembic upgrade
head`` падал на уже существующих таблицах. Теперь путь один.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from .session import Database

logger = logging.getLogger("kvitto")

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"
MIGRATIONS_DIR = ALEMBIC_INI.parent / "migrations"


def run_migrations(database_url: str, ini_path: Path | None = None) -> bool:
    """Приводит схему к актуальной. ``False`` — если Alembic недоступен."""
    ini_path = ini_path or ALEMBIC_INI
    if not ini_path.is_file() or not MIGRATIONS_DIR.is_dir():
        logger.warning("Alembic не найден (%s), пропускаю миграции", ini_path)
        return False

    config = Config(str(ini_path))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")
    return True


def prepare_schema(database: Database) -> None:
    """Миграции, если возможно; иначе — создание таблиц напрямую."""
    if run_migrations(database.url):
        logger.info("Схема актуальна (alembic upgrade head)")
        return
    database.create_all()
    logger.info("Схема создана через create_all")
