"""Бонусные сценарии: список платежей с фильтрами."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import standard_id


def create(client: TestClient, email: str) -> dict:
    response = client.post(
        "/payments",
        json={"tariff_id": standard_id(client), "email": email, "method": "card"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_list_payments_returns_all(client: TestClient):
    create(client, "a@example.com")
    create(client, "b@example.com")

    response = client.get("/payments")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_filter_by_email(client: TestClient):
    create(client, "a@example.com")
    create(client, "b@example.com")

    payments = client.get("/payments", params={"email": "a@example.com"}).json()

    assert len(payments) == 1
    assert payments[0]["email"] == "a@example.com"


def test_filter_by_status(client: TestClient):
    first = create(client, "a@example.com")
    create(client, "b@example.com")
    client.post("/webhooks/bank", json={"payment_id": first["id"], "status": "succeeded"})

    succeeded = client.get("/payments", params={"status": "succeeded"}).json()
    pending = client.get("/payments", params={"status": "pending"}).json()

    assert len(succeeded) == 1
    assert succeeded[0]["id"] == first["id"]
    assert len(pending) == 1
    assert pending[0]["email"] == "b@example.com"


def test_combined_filters(client: TestClient):
    first = create(client, "a@example.com")
    create(client, "b@example.com")
    client.post("/webhooks/bank", json={"payment_id": first["id"], "status": "succeeded"})

    payments = client.get(
        "/payments", params={"email": "a@example.com", "status": "succeeded"}
    ).json()

    assert len(payments) == 1


def test_pagination(client: TestClient):
    for index in range(5):
        create(client, f"student{index}@example.com")

    page = client.get("/payments", params={"limit": 2, "offset": 0}).json()
    next_page = client.get("/payments", params={"limit": 2, "offset": 2}).json()

    assert len(page) == 2
    assert len(next_page) == 2
    assert {p["id"] for p in page}.isdisjoint({p["id"] for p in next_page})


def test_unknown_filter_status_returns_422(client: TestClient):
    assert client.get("/payments", params={"status": "paid"}).status_code == 422
