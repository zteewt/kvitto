"""Проверка подписи вебхука (бонусное требование).

Подпись — HMAC-SHA256 от **сырого** тела запроса, секрет в
``WEBHOOK_SECRET``. Если секрет не задан, проверка выключена — так сервис
остаётся рабочим при локальном запуске без переменных окружения.
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-Signature"
SHA256_PREFIX = "sha256="


def compute_signature(body: bytes, secret: str) -> str:
    """Считает подпись тела запроса (hex-дайджест)."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, secret: str, provided: str | None) -> bool:
    """Сравнивает подпись за постоянное время.

    ``hmac.compare_digest`` вместо ``==`` — чтобы по времени ответа нельзя
    было подобрать подпись перебором.
    """
    if not secret:
        return True
    if not provided:
        return False
    candidate = provided.strip()
    if candidate.startswith(SHA256_PREFIX):
        candidate = candidate[len(SHA256_PREFIX) :]
    return hmac.compare_digest(compute_signature(body, secret), candidate)
