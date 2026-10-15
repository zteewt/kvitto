"""Тарифы."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .money import Money


class TariffCode(StrEnum):
    """Читаемый идентификатор тарифа, независимый от ``id`` в БД."""

    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"


@dataclass(frozen=True, slots=True)
class Tariff:
    """Тариф. ``price`` — полная цена в копейках."""

    id: int
    code: TariffCode
    title: str
    price: Money


#: Каталог, создаваемый при старте приложения: (код, название, цена в рублях).
DEFAULT_TARIFFS: tuple[tuple[TariffCode, str, int], ...] = (
    (TariffCode.BASIC, "Базовый", 9_900),
    (TariffCode.STANDARD, "Стандарт", 19_900),
    (TariffCode.PREMIUM, "Премиум", 29_900),
)


def build_default_tariffs() -> tuple[Tariff, ...]:
    """Каталог по умолчанию с последовательными id, начиная с 1."""
    return tuple(
        Tariff(id=index, code=code, title=title, price=Money.from_rubles(rubles))
        for index, (code, title, rubles) in enumerate(DEFAULT_TARIFFS, start=1)
    )
