"""Сценарий: список платежей с фильтрами (бонусное требование)."""

from __future__ import annotations

from collections.abc import Sequence

from kvitto.domain.payment import Payment
from kvitto.domain.ports import PaymentRepository

from .dto import ListPaymentsQuery


class ListPayments:
    def __init__(self, payments: PaymentRepository) -> None:
        self._payments = payments

    def execute(self, query: ListPaymentsQuery) -> Sequence[Payment]:
        return self._payments.list_by(
            email=query.email,
            status=query.status,
            limit=query.limit,
            offset=query.offset,
        )
