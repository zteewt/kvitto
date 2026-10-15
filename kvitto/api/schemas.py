"""Pydantic-схемы запросов и ответов.

Здесь живёт только валидация *формы* запроса. Бизнес-правила (допустимый
срок рассрочки, неизвестный промокод, запрещённый переход статуса) намеренно
не дублируются — их проверяет домен, а ``api/errors.py`` переводит доменные
ошибки в коды ответа.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from kvitto.domain.payment import Payment, PaymentMethod
from kvitto.domain.status import PaymentStatus
from kvitto.domain.tariff import Tariff

#: ТЗ: допустимы только 3, 6 или 12 месяцев — проверяет домен.
InstallmentMonths = int | None


class TariffResponse(BaseModel):
    """Тариф каталога. ``price`` — в копейках."""

    id: int
    code: str = Field(description="Код тарифа: basic / standard / premium")
    title: str
    price: int = Field(description="Полная цена в копейках")


class PaymentResponse(BaseModel):
    """Платёж во всех ответах. Все денежные поля — целые копейки."""

    id: int
    status: PaymentStatus
    tariff_id: int
    tariff_code: str | None = None
    amount: int = Field(description="Полная цена тарифа, копейки")
    discount: int = Field(description="Скидка по промокоду, копейки")
    amount_due: int = Field(description="К оплате: amount - discount, копейки")
    method: PaymentMethod
    installment_months: InstallmentMonths = None
    schedule: list[int] | None = Field(
        default=None, description="График рассрочки в копейках; null для card/sbp"
    )
    email: str
    created_at: datetime


class CreatePaymentRequest(BaseModel):
    """Тело ``POST /payments``."""

    model_config = ConfigDict(extra="forbid")

    tariff_id: int | str = Field(
        description='id тарифа или его код: 2 / "standard"',
    )
    email: EmailStr
    method: PaymentMethod
    installment_months: InstallmentMonths = Field(
        default=None,
        description="Обязателен для метода installment. Допустим 3, 6 или 12",
    )
    promo_code: str | None = Field(default=None, max_length=64)


class BankWebhookRequest(BaseModel):
    """Тело ``POST /webhooks/bank``."""

    model_config = ConfigDict(extra="forbid")

    payment_id: int
    status: PaymentStatus


class ListPaymentsQueryParams(BaseModel):
    """Фильтры ``GET /payments`` (бонусное требование)."""

    email: str | None = None
    status: PaymentStatus | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class WebhookResponse(BaseModel):
    """Тело успешного ответа на вебхук — как в ТЗ."""

    result: str = "ok"


def tariff_to_response(tariff: Tariff) -> TariffResponse:
    return TariffResponse(
        id=tariff.id,
        code=tariff.code.value,
        title=tariff.title,
        price=tariff.price.kopecks,
    )


def payment_to_response(payment: Payment, tariff_code: str | None = None) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        status=payment.status,
        tariff_id=payment.tariff_id,
        tariff_code=tariff_code,
        amount=payment.amount.kopecks,
        discount=payment.discount.kopecks,
        amount_due=payment.amount_due.kopecks,
        method=payment.method,
        installment_months=payment.installment_months,
        schedule=(
            [value.kopecks for value in payment.schedule] if payment.schedule is not None else None
        ),
        email=payment.email,
        created_at=payment.created_at,
    )
