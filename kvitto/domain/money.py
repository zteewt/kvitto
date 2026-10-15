"""Денежная сумма.

Во всём приложении деньги — это целое число копеек. ``float`` отвергается
на уровне типа: конструктор не даст создать ``Money(19.9)``.
"""

from __future__ import annotations

from dataclasses import dataclass

KOPECKS_IN_RUB = 100


@dataclass(frozen=True, order=True, slots=True)
class Money:
    """Величина денег в копейках. Неизменяемое значение (value object)."""

    kopecks: int

    def __post_init__(self) -> None:
        # bool — подкласс int, но суммой в копейках он быть не может.
        if isinstance(self.kopecks, bool) or not isinstance(self.kopecks, int):
            raise TypeError(
                f"Сумма должна быть целым числом копеек, а не {type(self.kopecks).__name__}"
            )
        if self.kopecks < 0:
            raise ValueError("Сумма не может быть отрицательной")

    @classmethod
    def zero(cls) -> Money:
        return cls(0)

    @classmethod
    def from_rubles(cls, rubles: int) -> Money:
        return cls(rubles * KOPECKS_IN_RUB)

    def percent_of(self, percent: int) -> Money:
        """Целочисленный процент от суммы.

        Округление всегда вниз (``//``): копейки, которых не хватило на
        целый процент, остаются у продавца. Для тарифов каталога 10%
        делятся ровно, поэтому округление на них не влияет.
        """
        if not 0 <= percent <= 100:
            raise ValueError(f"Процент должен быть в диапазоне 0..100, получено {percent}")
        return Money(self.kopecks * percent // 100)

    def __add__(self, other: Money) -> Money:
        return Money(self.kopecks + other.kopecks)

    def __sub__(self, other: Money) -> Money:
        if other.kopecks > self.kopecks:
            raise ValueError("Результат вычитания не может быть отрицательным")
        return Money(self.kopecks - other.kopecks)

    def __str__(self) -> str:
        rubles, kopecks = divmod(self.kopecks, KOPECKS_IN_RUB)
        return f"{rubles} руб. {kopecks:02d} коп."
