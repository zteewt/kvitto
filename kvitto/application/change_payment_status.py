"""Сценарий: смена статуса платежа по вебхуку банка."""

from __future__ import annotations

from kvitto.domain.exceptions import EntityNotFound
from kvitto.domain.ports import PaymentRepository

from .dto import ChangePaymentStatusCommand, ChangePaymentStatusResult


class ChangePaymentStatus:
    def __init__(self, payments: PaymentRepository) -> None:
        self._payments = payments

    def execute(self, command: ChangePaymentStatusCommand) -> ChangePaymentStatusResult:
        payment = self._payments.get(command.payment_id)
        if payment is None:
            raise EntityNotFound("Платёж", command.payment_id)

        # Агрегат сам решает, разрешён ли переход, и бросает до мутации.
        event = payment.change_status(command.target)
        self._payments.update(payment)
        return ChangePaymentStatusResult(payment=payment, event=event)
