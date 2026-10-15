"""Миграции Alembic: реальная схема совпадает с моделями."""

from __future__ import annotations

import sqlite3

from kvitto.infrastructure.db.schema import run_migrations
from kvitto.infrastructure.db.session import Database


def test_migrations_create_the_expected_schema(tmp_path):
    db_path = tmp_path / "migrated.db"
    url = f"sqlite:///{db_path}"

    assert run_migrations(url) is True

    connection = sqlite3.connect(db_path)
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"alembic_version", "tariffs", "payments"} <= tables

    columns = {row[1]: row[2] for row in connection.execute("PRAGMA table_info(payments)")}
    assert columns["amount"] == "BIGINT", "деньги должны храниться в BIGINT (копейки)"
    assert columns["discount"] == "BIGINT"
    assert columns["schedule"] == "JSON"
    connection.close()


def test_migrations_are_idempotent(tmp_path):
    """Повторный запуск не падает и не дублирует таблицы."""
    url = f"sqlite:///{tmp_path / 'twice.db'}"

    assert run_migrations(url) is True
    assert run_migrations(url) is True

    database = Database(url)
    connection = database.engine.connect()
    tables = {
        row[0]
        for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert len([name for name in tables if name == "payments"]) == 1
    connection.close()
    database.dispose()


def test_migrations_produce_the_same_schema_as_models(tmp_path):
    """Отсутствие дрейфа: миграции и модели описывают одну схему."""
    migrated_url = f"sqlite:///{tmp_path / 'migrated.db'}"
    models_url = f"sqlite:///{tmp_path / 'models.db'}"
    run_migrations(migrated_url)

    models_database = Database(models_url)
    models_database.create_all()
    models_database.dispose()

    def tables_of(url: str) -> dict[str, list[tuple[str, str]]]:
        database = Database(url)
        names = [
            row[0]
            for row in database.engine.connect().exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        snapshot = {
            name: [
                (row[1], row[2])
                for row in database.engine.connect().exec_driver_sql(f"PRAGMA table_info({name})")
            ]
            for name in names
        }
        database.dispose()
        return snapshot

    migrated = tables_of(migrated_url)
    from_models = tables_of(models_url)
    # alembic_version есть только у варианта с миграциями.
    migrated.pop("alembic_version", None)

    assert migrated == from_models


def test_app_starts_on_a_migrated_database(tmp_path):
    """Приложение поднимается на базе, созданной миграциями."""
    from fastapi.testclient import TestClient

    from kvitto.api.app import create_app
    from kvitto.api.settings import Settings

    url = f"sqlite:///{tmp_path / 'startup.db'}"
    run_migrations(url)

    app = create_app(Settings(database_url=url))
    with TestClient(app) as client:
        assert client.get("/tariffs").status_code == 200
