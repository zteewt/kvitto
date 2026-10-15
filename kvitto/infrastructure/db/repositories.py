"""Реализации портов на SQLAlchemy.

Здесь единственное место, где доменные объекты превращаются в строки
таблиц и обратно. Проверки валютности, промокодов и статусов живут
в домене — репозиторий их не дублирует.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kvitto.domain.exceptions import DuplicateIdempotencyKey
from kvitto.domain.money import Money
from kvitto.domain.payment import Payment, PaymentMethod
from kvitto.domain.ports import PaymentRepository, TariffRepository
from kvitto.domain.status import PaymentStatus
from kvitto.domain.tariff import Tariff, TariffCode

from .models import PaymentModel, TariffModel


def _as_utc(value: datetime) -> datetime:
    """SQLite не хранит часовой пояс — возвращаем осмысленный UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def tariff_to_model(tariff: Tariff) -> TariffModel:
    return TariffModel(
        id=tariff.id,
        code=tariff.code.value,
        title=tariff.title,
        price=tariff.price.kopecks,
    )


def _to_tariff(model: TariffModel) -> Tariff:
    return Tariff(
        id=model.id,
        code=TariffCode(model.code),
        title=model.title,
        price=Money(model.price),
    )


def _to_payment(model: PaymentModel) -> Payment:
    return Payment(
        id=model.id,
        tariff_id=model.tariff_id,
        amount=Money(model.amount),
        discount=Money(model.discount),
        method=PaymentMethod(model.method),
        email=model.email,
        installment_months=model.installment_months,
        schedule=(
            tuple(Money(value) for value in model.schedule) if model.schedule is not None else None
        ),
        status=PaymentStatus(model.status),
        idempotency_key=model.idempotency_key,
        created_at=_as_utc(model.created_at),
    )


def apply_payment(payment: Payment, model: PaymentModel) -> None:
    """Копирует состояние агрегата в строку таблицы."""
    model.tariff_id = payment.tariff_id
    model.amount = payment.amount.kopecks
    model.discount = payment.discount.kopecks
    model.method = payment.method.value
    model.email = payment.email
    model.installment_months = payment.installment_months
    model.schedule = (
        [value.kopecks for value in payment.schedule] if payment.schedule is not None else None
    )
    model.status = payment.status.value
    model.idempotency_key = payment.idempotency_key
    if payment.created_at is not None:
        model.created_at = payment.created_at


class SqlAlchemyTariffRepository(TariffRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> Sequence[Tariff]:
        models = self._session.scalars(select(TariffModel).order_by(TariffModel.id))
        return [_to_tariff(model) for model in models]

    def get_by_id(self, tariff_id: int) -> Tariff | None:
        model = self._session.get(TariffModel, tariff_id)
        return _to_tariff(model) if model else None

    def get_by_code(self, code: TariffCode) -> Tariff | None:
        model = self._session.scalar(select(TariffModel).where(TariffModel.code == code.value))
        return _to_tariff(model) if model else None

    def save_all(self, tariffs: Iterable[Tariff]) -> None:
        for tariff in tariffs:
            self._session.add(tariff_to_model(tariff))
        self._session.flush()


class SqlAlchemyPaymentRepository(PaymentRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, payment: Payment) -> Payment:
        model = PaymentModel()
        apply_payment(payment, model)
        self._session.add(model)
        try:
            self._session.flush()  # получаем id без коммита
        except IntegrityError as exc:
            # Гонка: параллельный запрос с тем же ключом вставил строку
            # раньше. Откатываем только неудачную вставку, чтобы вызывающий
            # мог прочитать уже сохранённую строку победившего запроса.
            self._session.rollback()
            raise DuplicateIdempotencyKey(payment.idempotency_key or "") from exc
        payment.id = model.id
        return payment

    def get(self, payment_id: int) -> Payment | None:
        model = self._session.get(PaymentModel, payment_id)
        return _to_payment(model) if model else None

    def find_by_idempotency_key(self, key: str) -> Payment | None:
        model = self._session.scalar(
            select(PaymentModel).where(PaymentModel.idempotency_key == key)
        )
        return _to_payment(model) if model else None

    def list_by(
        self,
        *,
        email: str | None = None,
        status: PaymentStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Payment]:
        statement = select(PaymentModel)
        if email is not None:
            statement = statement.where(PaymentModel.email == email)
        if status is not None:
            statement = statement.where(PaymentModel.status == status.value)
        statement = (
            statement.order_by(PaymentModel.created_at.desc(), PaymentModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_payment(model) for model in self._session.scalars(statement)]

    def update(self, payment: Payment) -> Payment:
        model = self._session.get(PaymentModel, payment.id)
        if model is None:
            raise LookupError(f"Платёж {payment.id} не найден")
        apply_payment(payment, model)
        self._session.flush()
        return payment
