from datetime import date

import pytest

from tallyclerk.parsing import (
    container_check_digit,
    normalize_hs,
    parse_date,
    parse_money,
    parse_number,
    parse_tolerance,
    parse_weight_kg,
    validate_container,
)


@pytest.mark.parametrize("raw, expected", [
    ("1,234.56", 1234.56),
    ("1.234,56", 1234.56),
    ("1 234,56", 1234.56),
    ("12,450", 12450.0),
    ("12,5", 12.5),
    ("1.234.567", 1234567.0),
    ("880 CTNS", 880.0),
    ("880 (EIGHT HUNDRED EIGHTY) CARTONS", 880.0),
    (42, 42.0),
    ("n/a", None),
    (None, None),
])
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


@pytest.mark.parametrize("raw, kg", [
    ("12,450.50 KGS", 12450.5),
    ("8064 KG", 8064.0),
    ("17,778 LBS", 17778 * 0.45359237),
    ("12.45 MT", 12450.0),
    ("3 metric tons", 3000.0),
    ("N.W. 1,000 KG", 1000.0),
    ("500", 500.0),
])
def test_parse_weight(raw, kg):
    assert parse_weight_kg(raw) == pytest.approx(kg)


@pytest.mark.parametrize("raw, expected", [
    ("USD 95,760.00", (95760.0, "USD")),
    ("$1,200", (1200.0, "USD")),
    ("48 960,00 EUR", (48960.0, "EUR")),
    ("1,000.00", (1000.0, None)),
])
def test_parse_money(raw, expected):
    assert parse_money(raw) == expected


@pytest.mark.parametrize("raw", [
    "2026-03-06", "06 MAR 2026", "06-Mar-2026", "March 6, 2026", "06.03.2026", "06/03/2026", "260306",
])
def test_parse_date_formats(raw):
    assert parse_date(raw) == date(2026, 3, 6)


def test_parse_date_rejects_garbage():
    assert parse_date("sometime in spring") is None
    assert parse_date("261399") is None


def test_parse_tolerance():
    assert parse_tolerance("10/10") == (10.0, 10.0)
    assert parse_tolerance("5/0") == (5.0, 0.0)
    assert parse_tolerance("5%") == (5.0, 5.0)
    assert parse_tolerance("none") is None


def test_iso6346_reference_example():
    # The worked example from the ISO 6346 standard.
    assert container_check_digit("CSQU305438") == 3
    assert validate_container("CSQU3054383") is None


def test_iso6346_detects_typos():
    assert validate_container("MSCU 481937 0") is None
    assert "expected 0" in validate_container("MSCU4819371")
    assert "format" in validate_container("MSC4819370")


def test_normalize_hs():
    assert normalize_hs("6109.10.00") == "61091000"
    assert normalize_hs("6109 10") == "610910"
