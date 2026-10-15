"""Платёж — агрегатный корень.

Единственное место, где живёт правило переходов статусов: наружу
отдаётся только ``change_status``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .events import PaymentStatusChanged
from .exceptions import InvalidStatusTransition
from .installment import InstallmentPlan
from .money import Money
from .pricing import Quote
from .status import INITIAL_STATUS, PaymentStatus, is_allowed_transition


class PaymentMethod(StrEnum):
    """Способ оплаты."""

    CARD = "card"
    SBP = "sbp"
    INSTALLMENT = "installment"


@dataclass(slots=True)
class Payment:
    """Платёж за тариф.

    ``amount`` — полная цена тарифа, ``discount`` — скидка,
    ``amount_due`` — сумма к оплате.
    """

    id: int | None
    tariff_id: int
    amount: Money
    discount: Money
    method: PaymentMethod
    email: str
    installment_months: int | None = None
    schedule: tuple[Money, ...] | None = None
    status: PaymentStatus = INITIAL_STATUS
    idempotency_key: str | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.discount > self.amount:
            raise ValueError("Скидка не может превышать цену тарифа")
        is_installment = self.method is PaymentMethod.INSTALLMENT
        if is_installment != (self.installment_months is not None):
            raise ValueError("Срок рассрочки задан только для метода installment")
        if is_installment != (self.schedule is not None):
            raise ValueError("График платежей задан только для метода installment")

    @property
    def amount_due(self) -> Money:
        """Сумма к оплате: цена минус скидка."""
        return self.amount - self.discount

    @classmethod
    def create(
        cls,
        *,
        tariff_id: int,
        email: str,
        method: PaymentMethod,
        quote: Quote,
        installment_months: int | None = None,
        idempotency_key: str | None = None,
        now: datetime | None = None,
    ) -> Payment:
        """Создаёт платёж в статусе ``pending``.

        Допущение (см. README): при ``method`` из ``card``/``sbp`` поле
        ``installment_months``, если пришло, игнорируется — график не
        строится, а в ответе приходит ``null``.
        """
        if method is PaymentMethod.INSTALLMENT:
            plan = InstallmentPlan.build(quote.due, installment_months)
            months: int | None = plan.months
            schedule: tuple[Money, ...] | None = plan.payments
        else:
            months, schedule = None, None

        return cls(
            id=None,
            tariff_id=tariff_id,
            amount=quote.amount,
            discount=quote.discount,
            method=method,
            email=email,
            installment_months=months,
            schedule=schedule,
            status=INITIAL_STATUS,
            idempotency_key=idempotency_key,
            created_at=now,
        )

    def change_status(self, target: PaymentStatus) -> PaymentStatusChanged | None:
        """Переводит платёж в новый статус.

        Запрещённый переход бросает исключение до любой мутации, поэтому
        статус платежа гарантированно остаётся прежним.
        """
        if not is_allowed_transition(self.status, target):
            raise InvalidStatusTransition(self.status, target)
        previous = self.status
        self.status = target
        if self.id is None:
            return None
        return PaymentStatusChanged(payment_id=self.id, previous=previous, current=target)
