"""Промокоды.

Промокод — значение, а не сущность: ``kvitto10``, `` KVITTO10 `` и
``KVITTO10`` — один и тот же промокод.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromoCode:
    """Промокод в нормализованном виде (без пробелов, верхний регистр)."""

    value: str

    @classmethod
    def parse(cls, raw: str) -> PromoCode:
        return cls(raw.strip().upper())

    def __str__(self) -> str:
        return self.value


#: Каталог промокодов: код -> процент скидки.
DEFAULT_PROMO_CODES: dict[str, int] = {"KVITTO10": 10}
