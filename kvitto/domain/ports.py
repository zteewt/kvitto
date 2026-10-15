"""Порты — интерфейсы, которые домен ожидает от внешнего мира.

Домен объявляет, что ему нужно (репозитории), инфраструктура отдаёт
реализации. Благодаря этому подмена SQLite на PostgreSQL не трогает
ни домен, ни сценарии.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence

from .payment import Payment
from .status import PaymentStatus
from .tariff import Tariff, TariffCode


class TariffRepository(ABC):
    """Хранилище тарифов."""

    @abstractmethod
    def list_all(self) -> Sequence[Tariff]:
        """Все тарифы каталога."""

    @abstractmethod
    def get_by_id(self, tariff_id: int) -> Tariff | None:
        """Тариф по числовому id или ``None``."""

    @abstractmethod
    def get_by_code(self, code: TariffCode) -> Tariff | None:
        """Тариф по коду (``basic``/``standard``/``premium``) или ``None``."""

    @abstractmethod
    def save_all(self, tariffs: Iterable[Tariff]) -> None:
        """Создаёт отсутствующие тарифы. Существующие не трогает."""


class PaymentRepository(ABC):
    """Хранилище платежей."""

    @abstractmethod
    def add(self, payment: Payment) -> Payment:
        """Сохраняет новый платёж и возвращает его с присвоенным id.

        Если ключ идемпотентности уже занят, поднимает
        :class:`~kvitto.domain.exceptions.DuplicateIdempotencyKey`: так
        инфраструктура прячет от сценария ``IntegrityError``.
        """

    @abstractmethod
    def get(self, payment_id: int) -> Payment | None:
        """Платёж по id или ``None``."""

    @abstractmethod
    def update(self, payment: Payment) -> Payment:
        """Сохраняет изменения существующего платежа."""

    @abstractmethod
    def find_by_idempotency_key(self, key: str) -> Payment | None:
        """Платёж с таким ключом идемпотентности или ``None``."""

    @abstractmethod
    def list_by(
        self,
        *,
        email: str | None = None,
        status: PaymentStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Payment]:
        """Список платежей с фильтрами (бонусное требование)."""
