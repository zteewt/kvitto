"""Сценарий: получить платёж по id."""

from __future__ import annotations

from kvitto.domain.exceptions import EntityNotFound
from kvitto.domain.payment import Payment
from kvitto.domain.ports import PaymentRepository


class GetPayment:
    def __init__(self, payments: PaymentRepository) -> None:
        self._payments = payments

    def execute(self, payment_id: int) -> Payment:
        payment = self._payments.get(payment_id)
        if payment is None:
            raise EntityNotFound("Платёж", payment_id)
        return payment
