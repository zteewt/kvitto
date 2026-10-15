"""POST /webhooks/bank — переходы статусов."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import standard_id


def make_payment(client: TestClient) -> int:
    response = client.post(
        "/payments",
        json={
            "tariff_id": standard_id(client),
            "email": "student@example.com",
            "method": "card",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def send(client: TestClient, payment_id: int, status: str):
    return client.post("/webhooks/bank", json={"payment_id": payment_id, "status": status})


def test_new_payment_is_pending(client: TestClient):
    assert client.get(f"/payments/{make_payment(client)}").json()["status"] == "pending"


def test_unknown_payment_returns_404(client: TestClient):
    response = send(client, 424242, "succeeded")
    assert response.status_code == 404


@pytest.mark.parametrize("status", ["succeeded", "failed"])
def test_allowed_transitions_from_pending(client: TestClient, status: str):
    payment_id = make_payment(client)

    response = send(client, payment_id, status)

    assert response.status_code == 200
    assert response.json() == {"result": "ok"}
    assert client.get(f"/payments/{payment_id}").json()["status"] == status


def test_refund_allowed_only_after_success(client: TestClient):
    payment_id = make_payment(client)
    send(client, payment_id, "succeeded")

    response = send(client, payment_id, "refunded")

    assert response.status_code == 200
    assert client.get(f"/payments/{payment_id}").json()["status"] == "refunded"


@pytest.mark.parametrize(
    ("prepare", "target"),
    [
        (None, "refunded"),  # pending -> refunded
        ("succeeded", "failed"),  # succeeded -> failed
        ("succeeded", "succeeded"),  # succeeded -> succeeded
        ("failed", "succeeded"),  # failed -> succeeded
        ("failed", "refunded"),  # failed -> refunded
        ("refunded", "succeeded"),  # refunded -> succeeded
    ],
    ids=[
        "pending->refunded",
        "succeeded->failed",
        "succeeded->succeeded",
        "failed->succeeded",
        "failed->refunded",
        "refunded->succeeded",
    ],
)
def test_forbidden_transition_returns_409_and_keeps_status(
    client: TestClient, read_payments, prepare: str | None, target: str
):
    payment_id = make_payment(client)
    if prepare == "refunded":
        send(client, payment_id, "succeeded")
        send(client, payment_id, "refunded")
    elif prepare is not None:
        send(client, payment_id, prepare)

    before = client.get(f"/payments/{payment_id}").json()["status"]
    response = send(client, payment_id, target)

    assert response.status_code == 409
    assert response.json() == {"error": "invalid_transition"}
    assert client.get(f"/payments/{payment_id}").json()["status"] == before


def test_forbidden_transition_does_not_touch_database(client: TestClient, read_payments):
    """Проверяем хранилище, а не только ответ клиенту."""
    payment_id = make_payment(client)
    send(client, payment_id, "succeeded")

    assert send(client, payment_id, "failed").status_code == 409

    stored = read_payments()
    assert len(stored) == 1
    assert stored[0].status.value == "succeeded"


@pytest.mark.parametrize("status", ["paid", "cancelled", "PENDING", ""])
def test_unknown_status_value_returns_422(client: TestClient, status: str):
    response = send(client, make_payment(client), status)
    assert response.status_code == 422


def test_full_success_lifecycle(client: TestClient):
    payment_id = make_payment(client)

    assert send(client, payment_id, "succeeded").status_code == 200
    assert send(client, payment_id, "refunded").status_code == 200
    assert client.get(f"/payments/{payment_id}").json()["status"] == "refunded"
    assert send(client, payment_id, "succeeded").status_code == 409
