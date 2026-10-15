"""Зависимости FastAPI."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from .container import ApplicationContainer
from .security import SIGNATURE_HEADER, verify_signature
from .settings import Settings

__all__ = [
    "SIGNATURE_HEADER",
    "ContainerDep",
    "IdempotencyKey",
    "get_container",
    "require_webhook_signature",
    "tariff_codes_by_id",
]

#: Заголовок идемпотентности; используется в POST /payments.
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=255)]


def get_container(request: Request) -> Iterator[ApplicationContainer]:
    """Даёт сценариям одну транзакцию на запрос.

    ``Database.session()`` коммитит при успешном выходе и откатывает при
    исключении, поэтому запрещённый переход статуса не может остаться
    в базе «наполовину применённым».
    """
    with request.app.state.database.session() as session:
        yield ApplicationContainer(session)


ContainerDep = Annotated[ApplicationContainer, Depends(get_container)]


def tariff_codes_by_id(container: ApplicationContainer) -> dict[int, str]:
    """Карта ``id -> код`` тарифа: один запрос вместо N+1 при сборке ответов."""
    return {tariff.id: tariff.code.value for tariff in container.tariffs.list_all()}


async def require_webhook_signature(request: Request) -> None:
    """Проверяет HMAC-подпись входящего вебхука, иначе 401.

    Тело читается до разбора: Starlette кэширует его в ``request._body``,
    поэтому Pydantic разберёт тело ниже по конвейеру как обычно.
    """
    settings: Settings = request.app.state.settings
    if not settings.webhook_secret:
        return

    body = await request.body()
    provided = request.headers.get(SIGNATURE_HEADER)
    if not verify_signature(body, settings.webhook_secret, provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверная подпись вебхука",
        )
