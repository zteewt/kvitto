"""Промокоды и расчёт суммы к оплате."""

from __future__ import annotations

import pytest

from kvitto.domain.exceptions import UnknownPromoCode
from kvitto.domain.money import Money
from kvitto.domain.pricing import QuoteCalculator
from kvitto.domain.promo import PromoCode
from kvitto.domain.tariff import Tariff, TariffCode


def test_without_promo_code(standard_quote):
    assert standard_quote.amount == Money(1_990_000)
    assert standard_quote.discount == Money.zero()
    assert standard_quote.due == Money(1_990_000)


@pytest.mark.parametrize(
    "raw",
    ["KVITTO10", "kvitto10", "KvItTo10", "  kvitto10  "],
)
def test_promo_code_ignores_case_and_spaces(raw: str, standard_tariff):
    quote = QuoteCalculator().quote(standard_tariff, PromoCode.parse(raw))
    assert quote.discount == Money(199_000)
    assert quote.due == Money(1_791_000)


def test_all_catalog_tariffs_get_ten_percent():
    calculator = QuoteCalculator()
    promo = PromoCode.parse("kvitto10")
    for price_rubles, discount_rubles in [(9_900, 990), (19_900, 1_990), (29_900, 2_990)]:
        tariff = Tariff(
            id=1,
            code=TariffCode.BASIC,
            title="Тариф",
            price=Money.from_rubles(price_rubles),
        )
        quote = calculator.quote(tariff, promo)
        assert quote.discount == Money.from_rubles(discount_rubles)
        assert quote.due == tariff.price - quote.discount


def test_unknown_promo_code_raises(standard_tariff):
    with pytest.raises(UnknownPromoCode) as exc_info:
        QuoteCalculator().quote(standard_tariff, PromoCode.parse("SUMMER"))
    assert exc_info.value.code == "SUMMER"


def test_empty_promo_code_is_unknown(standard_tariff):
    with pytest.raises(UnknownPromoCode):
        QuoteCalculator().quote(standard_tariff, PromoCode.parse("   "))
