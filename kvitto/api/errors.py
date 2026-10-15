"""Перевод доменных ошибок в HTTP-ответы.

Домен не знает про коды статуса — это единственное место, где решается,
какой код и какое тело вернуть клиенту.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from kvitto.domain.exceptions import (
    DomainError,
    EntityNotFound,
    InvalidInstallmentTerm,
    InvalidStatusTransition,
    UnknownPromoCode,
)

#: Формат 409 зафиксирован в ТЗ, остальное — стандартный формат FastAPI.
STATUS_BY_ERROR: dict[type[DomainError], int] = {
    EntityNotFound: 404,
    InvalidStatusTransition: 409,
    UnknownPromoCode: 422,
    InvalidInstallmentTerm: 422,
}


def build_error_response(exc: DomainError) -> JSONResponse:
    if isinstance(exc, InvalidStatusTransition):
        return JSONResponse(status_code=409, content={"error": "invalid_transition"})

    status_code = STATUS_BY_ERROR.get(type(exc), 400)
    # Стандартный ответ FastAPI для ошибок: {"detail": "..."}.
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        return build_error_response(exc)
