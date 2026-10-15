"""Сценарий: список тарифов каталога."""

from __future__ import annotations

from collections.abc import Sequence

from kvitto.domain.ports import TariffRepository
from kvitto.domain.tariff import Tariff


class ListTariffs:
    def __init__(self, tariffs: TariffRepository) -> None:
        self._tariffs = tariffs

    def execute(self) -> Sequence[Tariff]:
        return self._tariffs.list_all()
