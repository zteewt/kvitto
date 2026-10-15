"""Зависимости FastAPI."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request

from .container import ApplicationContainer

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
