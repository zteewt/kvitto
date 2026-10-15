from datetime import UTC, datetime

import pytest

from kvitto.domain.money import Money
from kvitto.domain.pricing import Quote, QuoteCalculator
from kvitto.domain.promo import PromoCode
from kvitto.domain.tariff import Tariff, TariffCode

NOW = datetime(2026, 1, 15, 10, 30, tzinfo=UTC)

STANDARD_TARIFF = Tariff(
    id=2,
    code=TariffCode.STANDARD,
    title="Стандарт",
    price=Money.from_rubles(19_900),
)


@pytest.fixture
def standard_tariff() -> Tariff:
    return STANDARD_TARIFF


@pytest.fixture
def standard_quote() -> Quote:
    """Расчёт по тарифу «Стандарт» без промокода."""
    return QuoteCalculator().quote(STANDARD_TARIFF)


@pytest.fixture
def promo_code() -> PromoCode:
    return PromoCode.parse("KVITTO10")
