"""Бонус: проверка HMAC-SHA256 подписи вебхука."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from kvitto.api.security import compute_signature
from tests.conftest import WEBHOOK_SECRET, standard_id


def body_of(payment_id: int, status: str) -> bytes:
    """Ровно те байты, которые подписывает банк."""
    return json.dumps({"payment_id": payment_id, "status": status}).encode("utf-8")


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


def post_signed(client: TestClient, payment_id: int, status: str, signature: str | None):
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-Signature"] = signature
    return client.post(
        "/webhooks/bank",
        content=body_of(payment_id, status),
        headers=headers,
    )


def test_valid_signature_is_accepted(secured_client: TestClient):
    payment_id = make_payment(secured_client)
    body = body_of(payment_id, "succeeded")

    response = post_signed(
        secured_client, payment_id, "succeeded", compute_signature(body, WEBHOOK_SECRET)
    )

    assert response.status_code == 200
    assert response.json() == {"result": "ok"}


def test_sha256_prefix_is_accepted(secured_client: TestClient):
    payment_id = make_payment(secured_client)
    body = body_of(payment_id, "succeeded")

    response = post_signed(
        secured_client, payment_id, "succeeded", f"sha256={compute_signature(body, WEBHOOK_SECRET)}"
    )

    assert response.status_code == 200


def test_invalid_signature_returns_401(secured_client: TestClient):
    payment_id = make_payment(secured_client)

    response = post_signed(secured_client, payment_id, "succeeded", "deadbeef")

    assert response.status_code == 401


def test_missing_signature_returns_401(secured_client: TestClient):
    payment_id = make_payment(secured_client)

    response = post_signed(secured_client, payment_id, "succeeded", None)

    assert response.status_code == 401


def test_signature_of_another_body_returns_401(secured_client: TestClient):
    payment_id = make_payment(secured_client)
    # Подпись от тела с другим статусом.
    other_body = body_of(payment_id, "refunded")

    response = post_signed(
        secured_client,
        payment_id,
        "succeeded",
        compute_signature(other_body, WEBHOOK_SECRET),
    )

    assert response.status_code == 401


def test_wrong_secret_returns_401(secured_client: TestClient):
    payment_id = make_payment(secured_client)
    body = body_of(payment_id, "succeeded")

    response = post_signed(
        secured_client, payment_id, "succeeded", compute_signature(body, "another-secret")
    )

    assert response.status_code == 401


@pytest.mark.parametrize("status", ["succeeded", "refunded"])
def test_rejected_webhook_does_not_change_status(secured_client: TestClient, status: str):
    payment_id = make_payment(secured_client)

    post_signed(secured_client, payment_id, status, "wrong-signature")

    assert secured_client.get(f"/payments/{payment_id}").json()["status"] == "pending"


def test_signature_check_runs_before_status_rules(secured_client: TestClient):
    """401 важнее 404/409: неподписанный запрос не должен раскрывать состояние."""
    response = secured_client.post(
        "/webhooks/bank",
        content=body_of(424242, "succeeded"),
        headers={"X-Signature": "wrong"},
    )
    assert response.status_code == 401


def test_without_secret_signature_is_not_required(client: TestClient):
    """Пустой WEBHOOK_SECRET не ломает обычный запуск сервиса."""
    payment_id = make_payment(client)

    response = client.post("/webhooks/bank", json={"payment_id": payment_id, "status": "succeeded"})

    assert response.status_code == 200
