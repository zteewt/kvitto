"""Статусы платежа и разрешённые переходы."""

from __future__ import annotations

from enum import StrEnum


class PaymentStatus(StrEnum):
    """Статус платежа. Значения совпадают с теми, что ждёт банк в вебхуке."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


#: Разрешённые переходы. Чего здесь нет — запрещено и даёт 409.
ALLOWED_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.PENDING: frozenset({PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}),
    PaymentStatus.SUCCEEDED: frozenset({PaymentStatus.REFUNDED}),
    PaymentStatus.FAILED: frozenset(),
    PaymentStatus.REFUNDED: frozenset(),
}

#: Статус нового платежа.
INITIAL_STATUS = PaymentStatus.PENDING


def is_allowed_transition(current: PaymentStatus, target: PaymentStatus) -> bool:
    """Разрешён ли переход ``current -> target``."""
    return target in ALLOWED_TRANSITIONS[current]
