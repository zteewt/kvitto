"""Общие фикстуры.

Доменные фикстуры работают без БД, интеграционные поднимают настоящее
приложение на временной SQLite — так тесты проверяют реальное поведение,
включая миграции, сид тарифов и маппинг доменных объектов в JSON.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from kvitto.api.app import create_app
from kvitto.api.settings import Settings
from kvitto.domain.money import Money
from kvitto.domain.payment import Payment
from kvitto.domain.pricing import Quote, QuoteCalculator
from kvitto.domain.promo import PromoCode
from kvitto.domain.tariff import Tariff, TariffCode
from kvitto.infrastructure.db.repositories import SqlAlchemyPaymentRepository

NOW = datetime(2026, 1, 15, 10, 30, tzinfo=UTC)

STANDARD_TARIFF = Tariff(
    id=2,
    code=TariffCode.STANDARD,
    title="Стандарт",
    price=Money.from_rubles(19_900),
)

WEBHOOK_SECRET = "test-webhook-secret"

# --- доменные фикстуры ------------------------------------------------------


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


# --- интеграционные фикстуры -----------------------------------------------


@pytest.fixture
def app(tmp_path):
    """Приложение на отдельной временной базе."""
    return create_app(Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}"))


@pytest.fixture
def secured_app(tmp_path):
    """Приложение с включённой проверкой подписи вебхука."""
    return create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'secured.db'}",
            webhook_secret=WEBHOOK_SECRET,
        )
    )


@pytest.fixture
def secured_client(secured_app) -> Iterator[TestClient]:
    with TestClient(secured_app) as secured_test_client:
        yield secured_test_client


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    """Клиент с запущенным lifespan: таблицы созданы, тарифы засеяны."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def read_payments(app) -> Callable[[], list[Payment]]:
    """Чтение платежей из БД мимо API.

    Нужно, чтобы тесты проверяли *результат*, а не только код ответа.
    """

    def _read() -> list[Payment]:
        with app.state.database.session() as session:
            return list(SqlAlchemyPaymentRepository(session).list_by(limit=500))

    return _read


def standard_id(client: TestClient) -> int:
    """id тарифа «Стандарт» из живого каталога."""
    tariffs = {item["code"]: item for item in client.get("/tariffs").json()}
    return tariffs["standard"]["id"]
