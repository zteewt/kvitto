"""Доменные события.

Факт произошедшего в домене. Приёмники живут снаружи (логи, метрики) —
внутри домена на них никто не подписан.
"""

from __future__ import annotations

from dataclasses import dataclass

from .status import PaymentStatus


@dataclass(frozen=True, slots=True)
class PaymentStatusChanged:
    """Статус платежа изменился."""

    payment_id: int
    previous: PaymentStatus
    current: PaymentStatus
