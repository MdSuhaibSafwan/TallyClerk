"""Checks that need only one document at a time."""

from __future__ import annotations

from ..parsing import validate_container
from ..reference import (
    CONTAINER_EQUIVALENT,
    INCOTERMS_2020,
    RETIRED_INCOTERMS,
    SEA_ONLY_INCOTERMS,
)
from .base import Context, Evidence, Hit, Severity, ev, rule


@rule("TC001", "Unreadable field value", Severity.WARNING)
def unreadable_values(ctx: Context):
    """A value is present on the document but could not be interpreted, so no
    check that depends on it can run. Usually an extraction problem."""
    for doc in ctx.documents:
        for name, problem in doc.issues:
            yield Hit(f"{name}: {problem}", [Evidence(doc.label, name, problem)])


@rule("TC002", "Invalid container number", Severity.ERROR, "ISO 6346")
def container_check_digit(ctx: Context):
    """Container numbers carry a check digit (ISO 6346). A wrong digit is
    almost always a typo, and cargo will not match the carrier's records."""
    for doc in ctx.documents:
        for number in doc.containers:
            problem = validate_container(number)
            if problem:
                yield Hit(f"{number} on {doc.label}: {problem}", [ev(doc, "containers", number)])


@rule("TC003", "Invoice arithmetic does not add up", Severity.ERROR)
def invoice_arithmetic(ctx: Context):
    """Each line must equal quantity x unit price, and the lines must sum to
    the invoice total."""
    tol = ctx.config.amount_tolerance
    for doc in ctx.of("commercial_invoice"):
        line_sum, complete = 0.0, bool(doc.items)
        for i, item in enumerate(doc.items, 1):
            if item.quantity is not None and item.unit_price is not None and item.amount is not None:
                expected = round(item.quantity * item.unit_price, 2)
                if abs(expected - item.amount) > tol:
                    yield Hit(
                        f"line {i} ({item.description or 'item'}): {item.quantity:g} x "
                        f"{item.unit_price:,.2f} = {expected:,.2f}, but the line says "
                        f"{item.amount:,.2f}",
                        [ev(doc, f"items[{i - 1}].amount", item.amount)],
                    )
            if item.amount is None:
                complete = False
            else:
                line_sum += item.amount
        if complete and doc.total_amount is not None and abs(line_sum - doc.total_amount) > tol:
            yield Hit(
                f"line items sum to {line_sum:,.2f} but the invoice total is "
                f"{doc.total_amount:,.2f}",
                [ev(doc, "total_amount")],
            )


@rule("TC004", "Net weight exceeds gross weight", Severity.ERROR)
def net_over_gross(ctx: Context):
    """Gross weight includes packaging, so it can never be below net weight."""
    for doc in ctx.documents:
        if doc.net_weight_kg and doc.gross_weight_kg and doc.net_weight_kg > doc.gross_weight_kg:
            yield Hit(
                f"{doc.label}: net {doc.net_weight_kg:,.2f} kg > gross "
                f"{doc.gross_weight_kg:,.2f} kg",
                [ev(doc, "net_weight"), ev(doc, "gross_weight")],
            )


@rule("TC005", "Invalid or outdated Incoterm", Severity.ERROR, "Incoterms 2020")
def incoterm_valid(ctx: Context):
    """The delivery term must be one of the eleven Incoterms 2020 rules."""
    for doc in ctx.documents:
        term = doc.incoterm
        if term is None or term in INCOTERMS_2020:
            continue
        reason = RETIRED_INCOTERMS.get(term, "not an Incoterms 2020 rule")
        yield Hit(f"{term} on {doc.label}: {reason}", [ev(doc, "incoterm")])


@rule("TC006", "Malformed HS code", Severity.WARNING, "WCO Harmonized System")
def hs_code_format(ctx: Context):
    """HS codes are numeric and at least 6 digits (national tariff lines are
    8 or 10). Anything else will be queried by customs."""
    for doc in ctx.documents:
        for i, item in enumerate(doc.items):
            code = item.hs_code
            if code and (not code.isdigit() or len(code) < 6 or len(code) > 10):
                yield Hit(
                    f"'{code}' ({item.description or 'item'}) on {doc.label}",
                    [ev(doc, f"items[{i}].hs_code", code)],
                )


@rule("TC007", "Sea-only Incoterm used for containerised cargo", Severity.INFO,
      "ICC Incoterms 2020 guidance")
def sea_term_for_containers(ctx: Context):
    """FOB/CFR/CIF/FAS transfer risk when goods are on board the vessel, but
    containers are handed over at a terminal days earlier. The ICC recommends
    FCA/CPT/CIP for container shipments."""
    containerised = any(d.containers for d in ctx.documents)
    if not containerised:
        return
    seen = set()
    for doc in ctx.documents:
        if doc.incoterm in SEA_ONLY_INCOTERMS and doc.incoterm not in seen:
            seen.add(doc.incoterm)
            yield Hit(
                f"{doc.incoterm} is used for a container shipment; consider "
                f"{CONTAINER_EQUIVALENT[doc.incoterm]}",
                [ev(doc, "incoterm")],
            )
