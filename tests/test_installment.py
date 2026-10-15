"""График рассрочки: сумма графика == сумма к оплате, всегда."""

from __future__ import annotations

import pytest

from kvitto.domain.exceptions import InvalidInstallmentTerm
from kvitto.domain.installment import InstallmentPlan
from kvitto.domain.money import Money


def test_example_from_spec():
    # Пример из ТЗ: standard без промокода, рассрочка на 3 месяца.
    plan = InstallmentPlan.build(Money(1_990_000), 3)
    assert plan.payments == (Money(663_334), Money(663_333), Money(663_333))
    assert plan.sum_payments == Money(1_990_000)


@pytest.mark.parametrize("months", [3, 6, 12])
@pytest.mark.parametrize(
    "total",
    [1_990_000, 1_791_000, 990_000, 2_990_000, 1, 7, 999_999],
    ids=str,
)
def test_schedule_sums_exactly_to_amount_due(months: int, total: int):
    plan = InstallmentPlan.build(Money(total), months)
    assert len(plan.payments) == months
    assert plan.sum_payments == Money(total)


@pytest.mark.parametrize("months", [3, 6, 12])
def test_extra_kopecks_go_to_the_first_payments(months: int):
    # base = 990_000 // months, остаток уходит в первые платежи.
    base, remainder = divmod(990_000, months)
    plan = InstallmentPlan.build(Money(990_000), months)
    expected = tuple(
        Money(base + 1) if index < remainder else Money(base) for index in range(months)
    )
    assert plan.payments == expected
    # Каждый платёж отличается от соседа не больше чем на одну копейку.
    assert max(p.kopecks for p in plan.payments) - min(p.kopecks for p in plan.payments) <= 1


def test_amount_smaller_than_term_is_allowed():
    plan = InstallmentPlan.build(Money(7), 12)
    assert len(plan.payments) == 12
    assert plan.sum_payments == Money(7)


@pytest.mark.parametrize("months", [0, 1, 2, 4, 5, 18, 24, -3])
def test_only_3_6_and_12_months_are_allowed(months: int):
    with pytest.raises(InvalidInstallmentTerm):
        InstallmentPlan.build(Money(1_990_000), months)


def test_plan_rejects_broken_invariant():
    with pytest.raises(ValueError, match="не равна"):
        InstallmentPlan(total=Money(100), months=3, payments=(Money(50), Money(50), Money(50)))
