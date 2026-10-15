"""Деньги: целые копейки, никакого float."""

from __future__ import annotations

import pytest

from kvitto.domain.money import Money


def test_rubles_to_kopecks():
    assert Money.from_rubles(19_900) == Money(1_990_000)


def test_float_is_rejected():
    with pytest.raises(TypeError):
        Money(199.0)  # type: ignore[arg-type]


def test_bool_is_rejected():
    # bool — подкласс int, но суммой быть не может.
    with pytest.raises(TypeError):
        Money(True)  # type: ignore[arg-type]


def test_negative_is_rejected():
    with pytest.raises(ValueError):
        Money(-1)


@pytest.mark.parametrize(
    ("kopecks", "expected"),
    [
        (990_000, 99_000),
        (1_990_000, 199_000),
        (2_990_000, 299_000),
    ],
)
def test_ten_percent_is_exact_for_every_catalog_tariff(kopecks: int, expected: int):
    assert Money(kopecks).percent_of(10) == Money(expected)


def test_percent_rounds_down():
    # 101 копейка, 10% = 10.1 -> 10, остаток у продавца.
    assert Money(101).percent_of(10) == Money(10)


def test_subtraction_cannot_go_negative():
    with pytest.raises(ValueError):
        Money(100) - Money(200)


def test_kopecks_stay_int_through_arithmetic():
    total = Money(1_990_000).percent_of(10) + Money(990)
    assert isinstance(total.kopecks, int)
