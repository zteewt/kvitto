"""POST /payments и GET /payments/{id} — деньги, промокоды, рассрочка."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import standard_id

STANDARD_PRICE = 1_990_000
PROMO_DISCOUNT = 199_000


def create_payment(client: TestClient, **overrides) -> dict:
    body = {
        "tariff_id": standard_id(client),
        "email": "student@example.com",
        "method": "card",
    }
    body.update(overrides)
    response = client.post("/payments", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_payment_without_promo(client: TestClient):
    payment = create_payment(client)

    assert payment["status"] == "pending"
    assert payment["amount"] == STANDARD_PRICE
    assert payment["discount"] == 0
    assert payment["amount_due"] == STANDARD_PRICE
    assert payment["method"] == "card"
    assert payment["installment_months"] is None
    assert payment["schedule"] is None
    assert payment["email"] == "student@example.com"
    assert payment["created_at"].endswith("Z")


def test_create_payment_with_promo_code(client: TestClient):
    payment = create_payment(client, promo_code="KVITTO10")

    assert payment["amount"] == STANDARD_PRICE
    assert payment["discount"] == PROMO_DISCOUNT
    assert payment["amount_due"] == STANDARD_PRICE - PROMO_DISCOUNT


@pytest.mark.parametrize("promo", ["KVITTO10", "kvitto10", "KvItTo10"])
def test_promo_code_ignores_case(client: TestClient, promo: str):
    assert create_payment(client, promo_code=promo)["discount"] == PROMO_DISCOUNT


def test_unknown_promo_code_returns_422(client: TestClient):
    response = client.post(
        "/payments",
        json={
            "tariff_id": standard_id(client),
            "email": "student@example.com",
            "method": "card",
            "promo_code": "SUMMER",
        },
    )
    assert response.status_code == 422
    assert "SUMMER" in response.text


def test_tariff_accepts_code_or_id(client: TestClient):
    by_id = create_payment(client, tariff_id=standard_id(client))
    by_code = create_payment(client, tariff_id="standard")
    assert by_id["tariff_id"] == by_code["tariff_id"] == standard_id(client)
    assert by_code["tariff_code"] == "standard"


def test_unknown_tariff_returns_404(client: TestClient):
    response = client.post(
        "/payments",
        json={"tariff_id": 999, "email": "student@example.com", "method": "card"},
    )
    assert response.status_code == 404


# --- рассрочка ---------------------------------------------------------------


@pytest.mark.parametrize("months", [3, 6, 12])
@pytest.mark.parametrize("promo", [None, "KVITTO10"])
def test_installment_schedule_sums_exactly_to_amount_due(
    client: TestClient, months: int, promo: str | None
):
    payment = create_payment(
        client,
        method="installment",
        installment_months=months,
        promo_code=promo,
    )

    expected_due = STANDARD_PRICE - (PROMO_DISCOUNT if promo else 0)
    assert payment["installment_months"] == months
    assert payment["amount_due"] == expected_due
    assert len(payment["schedule"]) == months
    assert sum(payment["schedule"]) == expected_due, "сумма графика должна равняться сумме к оплате"
    assert max(payment["schedule"]) - min(payment["schedule"]) <= 1


def test_installment_example_from_spec(client: TestClient):
    """Пример из ТЗ: standard без промокода, рассрочка на 3 месяца."""
    payment = create_payment(client, method="installment", installment_months=3)
    assert payment["schedule"] == [663_334, 663_333, 663_333]
    assert sum(payment["schedule"]) == STANDARD_PRICE


@pytest.mark.parametrize("months", [1, 2, 4, 24])
def test_installment_rejects_invalid_term(client: TestClient, months: int):
    response = client.post(
        "/payments",
        json={
            "tariff_id": standard_id(client),
            "email": "student@example.com",
            "method": "installment",
            "installment_months": months,
        },
    )
    assert response.status_code == 422


def test_installment_without_term_returns_422(client: TestClient):
    response = client.post(
        "/payments",
        json={
            "tariff_id": standard_id(client),
            "email": "student@example.com",
            "method": "installment",
        },
    )
    assert response.status_code == 422


def test_installment_months_ignored_for_card(client: TestClient):
    """Допущение из README: поле игнорируется, а не отвергается."""
    payment = create_payment(client, method="card", installment_months=6)
    assert payment["installment_months"] is None
    assert payment["schedule"] is None


# --- валидация и типы -------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"email": "student@example.com", "method": "card"},  # нет tariff_id
        {"tariff_id": 2, "method": "card"},  # нет email
        {"tariff_id": 2, "email": "не-email", "method": "card"},  # email невалиден
        {"tariff_id": 2, "email": "a@b.ru", "method": "crypto"},  # неизвестный метод
        {"tariff_id": 2, "email": "a@b.ru", "method": "card", "лишнее": 1},  # лишнее поле
    ],
)
def test_invalid_body_returns_422(client: TestClient, body: dict):
    response = client.post("/payments", json=body)
    assert response.status_code == 422


def test_money_fields_are_never_float(client: TestClient):
    """Ключевое требование ТЗ: никаких float в денежных полях."""
    payment = create_payment(
        client, promo_code="kvitto10", method="installment", installment_months=3
    )
    for field in ("amount", "discount", "amount_due"):
        assert isinstance(payment[field], int), f"{field} должен быть int"
        assert not isinstance(payment[field], float)
    assert all(isinstance(value, int) for value in payment["schedule"])


# --- чтение платежа ---------------------------------------------------------


def test_get_payment_by_id(client: TestClient):
    created = create_payment(client)
    response = client.get(f"/payments/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_payment_returns_404(client: TestClient):
    response = client.get("/payments/424242")
    assert response.status_code == 404


def test_created_payment_is_persisted(client: TestClient, read_payments):
    created = create_payment(client)
    stored = read_payments()

    assert len(stored) == 1
    assert stored[0].id == created["id"]
    assert stored[0].status.value == "pending"
    assert stored[0].amount.kopecks == created["amount"]
    assert stored[0].discount.kopecks == created["discount"]
