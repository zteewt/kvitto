"""Идемпотентность: повтор с тем же ключом не создаёт второй платёж."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import standard_id


def post_with_key(client: TestClient, key: str | None, **overrides):
    body = {
        "tariff_id": standard_id(client),
        "email": "student@example.com",
        "method": "card",
    }
    body.update(overrides)
    headers = {"Idempotency-Key": key} if key else {}
    return client.post("/payments", json=body, headers=headers)


def test_first_request_creates_payment(client: TestClient, read_payments):
    response = post_with_key(client, "order-1")

    assert response.status_code == 201
    assert len(read_payments()) == 1


def test_repeat_with_same_key_returns_existing_payment(client: TestClient, read_payments):
    first = post_with_key(client, "order-1")
    second = post_with_key(client, "order-1")

    assert first.status_code == 201
    assert second.status_code == 200, "повтор должен отвечать 200, а не 201"
    assert second.json()["id"] == first.json()["id"]
    assert second.json() == first.json()


def test_repeat_does_not_create_second_row(client: TestClient, read_payments):
    """Проверяем БД, а не только код ответа."""
    post_with_key(client, "order-1")
    post_with_key(client, "order-1")
    post_with_key(client, "order-1")

    assert len(read_payments()) == 1


def test_repeat_does_not_ignore_changed_body(client: TestClient, read_payments):
    """По ТЗ возвращается существующий платёж, даже если тело изменилось."""
    post_with_key(client, "order-1")
    second = post_with_key(client, "order-1", promo_code="KVITTO10")

    assert second.status_code == 200
    assert second.json()["discount"] == 0, "вернулся первый платёж, а не пересчитанный"
    assert len(read_payments()) == 1


def test_different_keys_create_separate_payments(client: TestClient, read_payments):
    first = post_with_key(client, "order-1")
    second = post_with_key(client, "order-2")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert len(read_payments()) == 2


def test_requests_without_key_are_not_deduplicated(client: TestClient, read_payments):
    first = post_with_key(client, None)
    second = post_with_key(client, None)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert len(read_payments()) == 2


def test_repeat_after_status_change_keeps_current_status(client: TestClient, read_payments):
    post_with_key(client, "order-1")
    payment_id = read_payments()[0].id

    client.post("/webhooks/bank", json={"payment_id": payment_id, "status": "succeeded"})
    second = post_with_key(client, "order-1")

    assert second.status_code == 200
    assert second.json()["status"] == "succeeded"
    assert len(read_payments()) == 1
