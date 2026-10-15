"""Время как зависимость — иначе тесты зависят от системных часов."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Источник «сей»."""

    def __call__(self) -> datetime: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


class FixedClock:
    """Часы для тестов: всегда возвращают один и тот же момент."""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def __call__(self) -> datetime:
        return self._moment
