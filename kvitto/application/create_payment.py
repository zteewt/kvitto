"""Сценарий: создать платёж.

Порядок шагов важен: идемпотентность проверяется **до** любой работы,
чтобы повторный запрос с тем же ключом не создал второй платёж.
"""

from __future__ import annotations

from kvitto.domain.exceptions import DuplicateIdempotencyKey, EntityNotFound
from kvitto.domain.payment import Payment
from kvitto.domain.ports import PaymentRepository, TariffRepository
from kvitto.domain.pricing import QuoteCalculator
from kvitto.domain.promo import PromoCode
from kvitto.domain.tariff import Tariff, TariffCode

from .clock import Clock, utc_now
from .dto import CreatePaymentCommand, CreatePaymentResult


class CreatePayment:
    """Создаёт платёж: тариф → промокод → график рассрочки → сохранение."""

    def __init__(
        self,
        tariffs: TariffRepository,
        payments: PaymentRepository,
        calculator: QuoteCalculator | None = None,
        clock: Clock = utc_now,
    ) -> None:
        self._tariffs = tariffs
        self._payments = payments
        self._calculator = calculator or QuoteCalculator()
        self._clock = clock

    def execute(self, command: CreatePaymentCommand) -> CreatePaymentResult:
        if command.idempotency_key is not None:
            existing = self._payments.find_by_idempotency_key(command.idempotency_key)
            if existing is not None:
                return CreatePaymentResult(payment=existing, created=False)

        tariff = self._resolve_tariff(command.tariff_ref)
        promo = PromoCode.parse(command.promo_code) if command.promo_code else None
        quote = self._calculator.quote(tariff, promo)

        payment = Payment.create(
            tariff_id=tariff.id,
            email=command.email,
            method=command.method,
            quote=quote,
            installment_months=command.installment_months,
            idempotency_key=command.idempotency_key,
            now=self._clock(),
        )

        try:
            saved = self._payments.add(payment)
        except DuplicateIdempotencyKey:
            return self._resolve_race(command)

        return CreatePaymentResult(payment=saved, created=True)

    def _resolve_tariff(self, reference: int | str) -> Tariff:
        """Принимает и числовой id, и код тарифа (допущение 1 в README)."""
        if isinstance(reference, int) and not isinstance(reference, bool):
            tariff = self._tariffs.get_by_id(reference)
        else:
            try:
                code = TariffCode(str(reference).strip().lower())
            except ValueError:
                raise EntityNotFound("Тариф", reference) from None
            tariff = self._tariffs.get_by_code(code)
        if tariff is None:
            raise EntityNotFound("Тариф", reference)
        return tariff

    def _resolve_race(self, command: CreatePaymentCommand) -> CreatePaymentResult:
        """Два параллельных запроса с одним ключом: побеждает первый."""
        if command.idempotency_key is None:
            raise
        winner = self._payments.find_by_idempotency_key(command.idempotency_key)
        if winner is None:
            raise
        return CreatePaymentResult(payment=winner, created=False)
