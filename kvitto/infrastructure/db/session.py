"""Подключение к БД и работа с сессиями.

По умолчанию — SQLite (ноль настройки, ``./kvitto.db``). Строка подключения
берётся из переменной окружения ``DATABASE_URL``, поэтому переезд на
PostgreSQL не затрагивает ни домен, ни сценарии.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .base import Base

DEFAULT_DATABASE_URL = "sqlite:///./kvitto.db"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_db_engine(url: str) -> Engine:
    """Создаёт движок. Для SQLite включает внешние ключи и потокобезопасность."""
    is_sqlite = url.startswith("sqlite")
    engine = create_engine(
        url,
        echo=False,
        # FastAPI живёт в потоках пула, а сессии закрываются там же, где открылись.
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


class Database:
    """Тонкая обёртка над движком: unit of work в одном методе."""

    def __init__(self, url: str | None = None) -> None:
        self.url = url or get_database_url()
        self.engine = create_db_engine(self.url)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

    def create_all(self) -> None:
        """Создаёт таблицы, если их ещё нет."""
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Открывает сессию: коммит на успех, откат на ошибку."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
