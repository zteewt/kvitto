"""Команды и результаты сценариев.

Обычные ``dataclass``, а не Pydantic: данные приходят уже проверенными
схемами из ``api/schemas.py``, а тащить Pydantic в прикладной слой
не нужно.
"""

from __future__ import annotations

from dataclasses import dataclass

from kvitto.domain.events import PaymentStatusChanged
from kvitto.domain.payment import Payment, PaymentMethod
from kvitto.domain.status import PaymentStatus


@dataclass(frozen=True, slots=True)
class CreatePaymentCommand:
    """Запрос на создание платежа (уже провалидированный)."""

    tariff_ref: int | str
    """id тарифа или его код (``2`` или ``"standard"``)."""

    email: str
    method: PaymentMethod
    installment_months: int | None = None
    promo_code: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class CreatePaymentResult:
    payment: Payment
    created: bool
    """``True`` — платёж создан (201), ``False`` — повтор по ключу (200)."""


@dataclass(frozen=True, slots=True)
class ChangePaymentStatusCommand:
    payment_id: int
    target: PaymentStatus


@dataclass(frozen=True, slots=True)
class ChangePaymentStatusResult:
    payment: Payment
    event: PaymentStatusChanged | None = None


@dataclass(frozen=True, slots=True)
class ListPaymentsQuery:
    email: str | None = None
    status: PaymentStatus | None = None
    limit: int = 50
    offset: int = 0
