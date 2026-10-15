"""Создание каталога тарифов при старте приложения.

Идемпотентно: при перезапуске существующие тарифы не трогаются.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from kvitto.domain.tariff import build_default_tariffs

from .repositories import SqlAlchemyTariffRepository


def seed_tariffs(session: Session) -> list[str]:
    """Добавляет недостающие тарифы из каталога по умолчанию."""
    repository = SqlAlchemyTariffRepository(session)
    existing_codes = {tariff.code for tariff in repository.list_all()}
    missing = [tariff for tariff in build_default_tariffs() if tariff.code not in existing_codes]
    repository.save_all(missing)
    return [tariff.code.value for tariff in missing]
