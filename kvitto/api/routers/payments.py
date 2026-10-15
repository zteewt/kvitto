"""``POST /payments``, ``GET /payments/{id}``, ``GET /payments``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from kvitto.api.deps import ContainerDep, IdempotencyKey, tariff_codes_by_id
from kvitto.api.schemas import (
    RESPONSES_ERRORS,
    RESPONSES_REPLAYED,
    CreatePaymentRequest,
    PaymentResponse,
    payment_to_response,
)
from kvitto.application.dto import CreatePaymentCommand, ListPaymentsQuery
from kvitto.domain.status import PaymentStatus

router = APIRouter(tags=["payments"])


@router.post(
    "/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать платёж",
    description=(
        "Создаёт платёж в статусе `pending`. "
        "С заголовком `Idempotency-Key` повторный запрос с тем же ключом "
        "возвращает уже созданный платёж с кодом 200 и не создаёт второй."
    ),
    responses={**RESPONSES_REPLAYED, **RESPONSES_ERRORS},
)
def create_payment(
    payload: CreatePaymentRequest,
    response: Response,
    container: ContainerDep,
    idempotency_key: IdempotencyKey = None,
) -> PaymentResponse:
    result = container.create_payment.execute(
        CreatePaymentCommand(
            tariff_ref=payload.tariff_id,
            email=str(payload.email),
            method=payload.method,
            installment_months=payload.installment_months,
            promo_code=payload.promo_code,
            idempotency_key=idempotency_key,
        )
    )
    if not result.created:
        # Повтор по ключу идемпотентности: платёж уже существует.
        response.status_code = status.HTTP_200_OK

    codes = tariff_codes_by_id(container)
    return payment_to_response(result.payment, codes.get(result.payment.tariff_id))


@router.get(
    "/payments/{payment_id}",
    response_model=PaymentResponse,
    summary="Платёж по id",
    responses={**RESPONSES_ERRORS},
)
def get_payment(payment_id: Annotated[int, Path(ge=1)], container: ContainerDep) -> PaymentResponse:
    payment = container.get_payment.execute(payment_id)
    codes = tariff_codes_by_id(container)
    return payment_to_response(payment, codes.get(payment.tariff_id))


@router.get(
    "/payments",
    response_model=list[PaymentResponse],
    summary="Список платежей с фильтрами",
    description="Бонусное требование: фильтры по `email` и `status`.",
    responses={**RESPONSES_ERRORS},
)
def list_payments(
    container: ContainerDep,
    email: Annotated[str | None, Query(description="Фильтр по email")] = None,
    payment_status: Annotated[
        PaymentStatus | None,
        Query(alias="status", description="Фильтр по статусу платежа"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PaymentResponse]:
    query = ListPaymentsQuery(email=email, status=payment_status, limit=limit, offset=offset)
    codes = tariff_codes_by_id(container)
    return [
        payment_to_response(payment, codes.get(payment.tariff_id))
        for payment in container.list_payments.execute(query)
    ]
