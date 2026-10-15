"""Настройки приложения (12-factor: всё из окружения)."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_DATABASE_URL = "sqlite:///./kvitto.db"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = DEFAULT_DATABASE_URL
    webhook_secret: str = ""
    """Секрет для HMAC-подписи вебхуков. Пусто — проверка подписи выключена."""

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
            webhook_secret=os.getenv("WEBHOOK_SECRET", ""),
        )
