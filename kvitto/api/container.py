"""Композиционный корень.

Единственное место, где конкретные реализации портов (SQLAlchemy)
связываются со сценариями. Прикладной слой об этом не знает — поэтому
подмена хранилища не затрагивает ни домен, ни роутеры.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from kvitto.application.change_payment_status import ChangePaymentStatus
from kvitto.application.clock import Clock, utc_now
from kvitto.application.create_payment import CreatePayment
from kvitto.application.get_payment import GetPayment
from kvitto.application.list_payments import ListPayments
from kvitto.application.list_tariffs import ListTariffs
from kvitto.infrastructure.db.repositories import (
    SqlAlchemyPaymentRepository,
    SqlAlchemyTariffRepository,
)


class ApplicationContainer:
    """Сценарии, собранные поверх одной сессии БД."""

    def __init__(self, session: Session, clock: Clock = utc_now) -> None:
        self.session = session

        self.tariffs = SqlAlchemyTariffRepository(session)
        self.payments = SqlAlchemyPaymentRepository(session)

        self.create_payment = CreatePayment(self.tariffs, self.payments, clock=clock)
        self.get_payment = GetPayment(self.payments)
        self.list_tariffs = ListTariffs(self.tariffs)
        self.change_payment_status = ChangePaymentStatus(self.payments)
        self.list_payments = ListPayments(self.payments)
