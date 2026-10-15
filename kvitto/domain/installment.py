"""График платежей по рассрочке."""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import InvalidInstallmentTerm
from .money import Money

#: Разрешённые сроки рассрочки (ТЗ).
ALLOWED_INSTALLMENT_MONTHS = frozenset({3, 6, 12})


@dataclass(frozen=True, slots=True)
class InstallmentPlan:
    """График платежей.

    Инвариант, который гарантирует конструктор: сумма платежей графика
    в точности равна сумме к оплате.
    """

    total: Money
    months: int
    payments: tuple[Money, ...]

    def __post_init__(self) -> None:
        if len(self.payments) != self.months:
            raise ValueError("Количество платежей должно совпадать со сроком рассрочки")
        if self.sum_payments != self.total:
            raise ValueError(
                f"Сумма графика {self.sum_payments} не равна сумме к оплате {self.total}"
            )

    @classmethod
    def build(cls, total: Money, months: int) -> InstallmentPlan:
        """Делит сумму на ``months`` частей.

        Копейки, оставшиеся от деления, раздаются по одной в первые
        платежи: 1990000 на 3 месяца -> (663334, 663333, 663333).
        """
        if months not in ALLOWED_INSTALLMENT_MONTHS:
            raise InvalidInstallmentTerm(months)
        base, remainder = divmod(total.kopecks, months)
        payments = tuple(
            Money(base + 1) if index < remainder else Money(base) for index in range(months)
        )
        return cls(total=total, months=months, payments=payments)

    @property
    def sum_payments(self) -> Money:
        return Money(sum((payment.kopecks for payment in self.payments), start=0))
