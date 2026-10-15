"""Платёж: создание, инварианты и переходы статусов."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kvitto.domain.exceptions import InvalidInstallmentTerm, InvalidStatusTransition
from kvitto.domain.money import Money
from kvitto.domain.payment import Payment, PaymentMethod
from kvitto.domain.pricing import QuoteCalculator
from kvitto.domain.promo import PromoCode
from kvitto.domain.status import PaymentStatus

NOW = datetime(2026, 1, 15, 10, 30, tzinfo=UTC)


def make_payment(standard_tariff, **overrides) -> Payment:
    """Создаёт платёж по тарифу «Стандарт» (1 990 000 копеек)."""
    promo = overrides.pop("promo_code", None)
    quote = QuoteCalculator().quote(standard_tariff, PromoCode.parse(promo) if promo else None)
    kwargs = {
        "tariff_id": standard_tariff.id,
        "email": "student@example.com",
        "method": PaymentMethod.CARD,
        "quote": quote,
        "now": NOW,
    }
    kwargs.update(overrides)
    return Payment.create(**kwargs)


def test_new_payment_is_pending(standard_tariff):
    payment = make_payment(standard_tariff)
    assert payment.status is PaymentStatus.PENDING
    assert payment.amount == Money(1_990_000)
    assert payment.discount == Money.zero()
    assert payment.amount_due == Money(1_990_000)
    assert payment.schedule is None
    assert payment.installment_months is None


def test_amount_due_accounts_for_promo(standard_tariff):
    payment = make_payment(standard_tariff, promo_code="kvitto10")
    assert payment.amount == Money(1_990_000)
    assert payment.discount == Money(199_000)
    assert payment.amount_due == Money(1_791_000)


def test_installment_builds_schedule(standard_tariff):
    payment = make_payment(
        standard_tariff,
        method=PaymentMethod.INSTALLMENT,
        installment_months=6,
    )
    assert payment.installment_months == 6
    assert payment.schedule is not None
    assert len(payment.schedule) == 6
    assert Money(sum(p.kopecks for p in payment.schedule)) == payment.amount_due


def test_installment_schedule_follows_promo(standard_tariff):
    payment = make_payment(
        standard_tariff,
        method=PaymentMethod.INSTALLMENT,
        installment_months=3,
        promo_code="KVITTO10",
    )
    assert payment.amount_due == Money(1_791_000)
    assert sum(p.kopecks for p in payment.schedule) == 1_791_000


def test_installment_requires_term(standard_tariff):
    with pytest.raises(InvalidInstallmentTerm):
        make_payment(standard_tariff, method=PaymentMethod.INSTALLMENT)


def test_installment_term_is_ignored_for_card(standard_tariff):
    """Допущение из README: поле игнорируется, а не отвергается."""
    payment = make_payment(standard_tariff, method=PaymentMethod.CARD, installment_months=6)
    assert payment.installment_months is None
    assert payment.schedule is None


def test_allowed_transitions_chain(standard_tariff):
    payment = make_payment(standard_tariff)
    payment.id = 1

    event = payment.change_status(PaymentStatus.SUCCEEDED)
    assert payment.status is PaymentStatus.SUCCEEDED
    assert event is not None
    assert (event.previous, event.current) == (PaymentStatus.PENDING, PaymentStatus.SUCCEEDED)

    payment.change_status(PaymentStatus.REFUNDED)
    assert payment.status is PaymentStatus.REFUNDED


@pytest.mark.parametrize(
    ("reached", "forbidden"),
    [
        ((), PaymentStatus.REFUNDED),
        ((PaymentStatus.SUCCEEDED,), PaymentStatus.SUCCEEDED),
        ((PaymentStatus.SUCCEEDED,), PaymentStatus.FAILED),
        ((PaymentStatus.FAILED,), PaymentStatus.SUCCEEDED),
        ((PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED), PaymentStatus.SUCCEEDED),
    ],
    ids=[
        "pending->refunded",
        "succeeded->succeeded",
        "succeeded->failed",
        "failed->succeeded",
        "refunded->succeeded",
    ],
)
def test_forbidden_transition_does_not_change_status(
    standard_tariff,
    reached: tuple[PaymentStatus, ...],
    forbidden: PaymentStatus,
):
    payment = make_payment(standard_tariff)
    payment.id = 1
    for status in reached:
        payment.change_status(status)

    before = payment.status
    with pytest.raises(InvalidStatusTransition) as exc_info:
        payment.change_status(forbidden)

    assert exc_info.value.current is before
    assert payment.status is before, "запрещённый переход не должен менять статус"
