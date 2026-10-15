"""Ошибки предметной области.

Домен ничего не знает про HTTP-коды: что превратить ту или иную ошибку
в 404/409/422, решает ``api/errors.py``.
"""

from __future__ import annotations

from .status import PaymentStatus


class DomainError(Exception):
    """Базовая ошибка домена."""


class EntityNotFound(DomainError):
    """Запрошенной сущности нет."""

    def __init__(self, entity: str, identifier: object) -> None:
        super().__init__(f"{entity} {identifier!r} не найден")
        self.entity = entity
        self.identifier = identifier


class UnknownPromoCode(DomainError):
    """Промокод не найден в каталоге."""

    def __init__(self, code: str) -> None:
        super().__init__(f"Неизвестный промокод: {code!r}")
        self.code = code


class InvalidInstallmentTerm(DomainError):
    """Срок рассрочки не входит в разрешённый набор."""

    def __init__(self, months: object) -> None:
        super().__init__(f"Недопустимый срок рассрочки: {months!r}")
        self.months = months


class InvalidStatusTransition(DomainError):
    """Платёж нельзя перевести в запрошенный статус."""

    def __init__(self, current: PaymentStatus, target: PaymentStatus) -> None:
        super().__init__(f"Переход {current} -> {target} запрещён")
        self.current = current
        self.target = target
