"""Сборка FastAPI-приложения.

``create_app`` — фабрика: приложение можно создать с любой БД, что удобно
для тестов (каждый тест получает свою временную базу).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from kvitto.infrastructure.db.schema import prepare_schema
from kvitto.infrastructure.db.seed import seed_tariffs
from kvitto.infrastructure.db.session import Database

from .errors import register_exception_handlers
from .routers import payments, tariffs, webhooks
from .settings import Settings

logger = logging.getLogger("kvitto")

API_TITLE = "Квитто API"
API_VERSION = "1.0.0"
API_DESCRIPTION = "API приёма оплаты курсов онлайн-школы."


def create_app(settings: Settings | None = None) -> FastAPI:
    """Создаёт приложение. Тарифы создаются при старте, идемпотентно."""
    resolved = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(resolved.database_url)
        prepare_schema(database)
        with database.session() as session:
            created_codes = seed_tariffs(session)
        if created_codes:
            logger.info("Созданы тарифы: %s", ", ".join(created_codes))
        app.state.database = database
        app.state.settings = resolved
        try:
            yield
        finally:
            database.dispose()

    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        lifespan=lifespan,
    )
    register_exception_handlers(app)

    app.include_router(tariffs.router)
    app.include_router(payments.router)
    app.include_router(webhooks.router)

    @app.get("/health", tags=["service"], summary="Проверка живости")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
