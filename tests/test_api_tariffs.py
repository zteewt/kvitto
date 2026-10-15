"""Тарифы: создаются при старте, цены — в копейках."""

from __future__ import annotations

from fastapi.testclient import TestClient

EXPECTED_CATALOG = [
    {"id": 1, "code": "basic", "title": "Базовый", "price": 990_000},
    {"id": 2, "code": "standard", "title": "Стандарт", "price": 1_990_000},
    {"id": 3, "code": "premium", "title": "Премиум", "price": 2_990_000},
]


def test_tariffs_are_created_on_startup(client: TestClient):
    response = client.get("/tariffs")
    assert response.status_code == 200
    assert response.json() == EXPECTED_CATALOG


def test_tariff_prices_are_integers(client: TestClient):
    for tariff in client.get("/tariffs").json():
        assert isinstance(tariff["price"], int)
        assert not isinstance(tariff["price"], float)


def test_tariffs_are_not_duplicated_on_restart(app):
    from fastapi.testclient import TestClient

    with TestClient(app):
        pass
    with TestClient(app) as second_client:
        assert len(second_client.get("/tariffs").json()) == 3


def test_health(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}
