"""Расчёт стоимости: полная цена, скидка и сумма к оплате."""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import UnknownPromoCode
from .money import Money
from .promo import DEFAULT_PROMO_CODES, PromoCode
from .tariff import Tariff


@dataclass(frozen=True, slots=True)
class Quote:
    """Результат расчёта.

    ``amount``  — полная цена тарифа,
    ``discount`` — размер скидки,
    ``due``     — сколько реально платит клиент (``amount - discount``).
    """

    amount: Money
    discount: Money

    @property
    def due(self) -> Money:
        return self.amount - self.discount


class QuoteCalculator:
    """Применяет промокод к цене тарифа."""

    def __init__(self, promo_codes: dict[str, int] | None = None) -> None:
        codes = DEFAULT_PROMO_CODES if promo_codes is None else promo_codes
        self._promo_codes = {code.strip().upper(): percent for code, percent in codes.items()}

    def quote(self, tariff: Tariff, promo_code: PromoCode | None = None) -> Quote:
        discount = Money.zero()
        if promo_code is not None:
            percent = self._promo_codes.get(promo_code.value)
            if percent is None:
                raise UnknownPromoCode(promo_code.value)
            discount = tariff.price.percent_of(percent)
        return Quote(amount=tariff.price, discount=discount)
