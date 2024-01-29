"""Parsers for the loosely formatted values found on trade documents.

Documents come from many countries and systems, so a weight may be written
``"12,450.50 KGS"``, ``"27,448 LBS"`` or ``"12.45 MT"``, and a date may be
``"2026-03-14"``, ``"14 MAR 2026"`` or the SWIFT MT700 form ``"260314"``.
Every parser here returns ``None`` for input it cannot interpret instead of
guessing, and callers record that as an issue on the document.
"""

from __future__ import annotations

import re
from datetime import date, datetime

_NUMBER = re.compile(r"[-+]?\d[\d.,'\s]*")
_THOUSANDS = re.compile(r"^\d{1,3}(?:[,]\d{3})+$")


def parse_number(value: object) -> float | None:
    """Parse ``1,234.56``, ``1.234,56``, ``1 234,56`` and plain numbers.

    When only one separator kind is present, a comma is a thousands separator
    if it groups digits in threes (``12,450``) and a decimal mark otherwise
    (``12,5``). A single dot is always a decimal mark.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUMBER.search(str(value))
    if not match:
        return None
    raw = re.sub(r"[\s']", "", match.group()).rstrip(".,")
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", "") if _THOUSANDS.match(raw.lstrip("+-")) else raw.replace(",", ".")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


_KG_PER_UNIT = {
    "kg": 1.0, "kgs": 1.0, "kilo": 1.0, "kilos": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237, "pounds": 0.45359237,
    "t": 1000.0, "mt": 1000.0, "ton": 1000.0, "tons": 1000.0, "tonne": 1000.0,
    "tonnes": 1000.0, "metric ton": 1000.0, "metric tons": 1000.0,
    "g": 0.001, "gr": 0.001, "gram": 0.001, "grams": 0.001,
}
_UNIT = re.compile(
    r"\b(metric tons?|kilograms?|kilos?|kgs?|tonnes?|tons?|mt|t|lbs?|pounds?|grams?|gr|g)\b", re.I
)


def parse_weight_kg(value: object) -> float | None:
    """Parse a weight into kilograms. A number with no unit is taken to be kilograms."""
    number = parse_number(value)
    if number is None or isinstance(value, (int, float)):
        return number
    unit = _UNIT.search(str(value))
    if unit is None:
        return number
    return number * _KG_PER_UNIT[unit.group(1).lower()]


_SYMBOLS = {"US$": "USD", "$": "USD", "€": "EUR", "£": "GBP", "₺": "TRY", "৳": "BDT"}
_CURRENCY = re.compile(r"\b([A-Z]{3})\b")


def parse_money(value: object) -> tuple[float | None, str | None]:
    """Parse ``"USD 48,960.00"``, ``"$48,960"`` or ``"48960 EUR"``."""
    amount = parse_number(value)
    if isinstance(value, (int, float)) or value is None:
        return amount, None
    text = str(value).strip()
    for symbol, code in _SYMBOLS.items():
        if symbol in text:
            return amount, code
    code = _CURRENCY.search(text.upper())
    return amount, code.group(1) if code else None


_DATE_FORMATS = (
    "%Y-%m-%d", "%d %b %Y", "%d-%b-%Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y",
    "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%b-%y",
)


def parse_date(value: object) -> date | None:
    """Parse common document date formats, including SWIFT ``YYMMDD``.

    Slash dates are read day-first (``14/03/2026``), which is the convention
    on the overwhelming majority of international trade documents.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if re.fullmatch(r"\d{6}", text):
        try:
            return datetime.strptime(text, "%y%m%d").date()
        except ValueError:
            return None
    text = text.title() if re.search(r"[A-Za-z]", text) else text
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_tolerance(value: object) -> tuple[float, float] | None:
    """Parse an LC amount tolerance: ``"10/10"`` (MT700 field 39A), ``"5%"``, ``5``."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value), float(value)
    parts = re.findall(r"\d+(?:\.\d+)?", str(value))
    if len(parts) == 1:
        return float(parts[0]), float(parts[0])
    if len(parts) == 2:
        return float(parts[0]), float(parts[1])
    return None


# ISO 6346 container numbers: 3-letter owner code, category (U/J/Z),
# 6-digit serial and a check digit computed over the first ten characters.
_CONTAINER = re.compile(r"^([A-Z]{3})([UJZ])(\d{6})(\d)$")
_LETTER_VALUES = {}
_v = 10
for _ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    if _v % 11 == 0:
        _v += 1
    _LETTER_VALUES[_ch] = _v
    _v += 1


def normalize_container(value: str) -> str:
    return re.sub(r"[\s\-/.]", "", str(value)).upper()


def container_check_digit(first_ten: str) -> int:
    """Compute the ISO 6346 check digit for an owner code + category + serial."""
    total = 0
    for i, ch in enumerate(first_ten.upper()):
        n = _LETTER_VALUES[ch] if ch.isalpha() else int(ch)
        total += n * (2 ** i)
    return total % 11 % 10


def validate_container(value: str) -> str | None:
    """Return ``None`` if the container number is valid, else the reason."""
    number = normalize_container(value)
    if not _CONTAINER.match(number):
        return "not in ISO 6346 format (e.g. MSKU1234565)"
    expected = container_check_digit(number[:10])
    if int(number[10]) != expected:
        return f"check digit is {number[10]}, expected {expected}"
    return None


def normalize_hs(value: object) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"[\s.\-]", "", str(value))
    return digits or None
