"""Checks that compare the same fact across several documents."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from typing import TypeVar

from ..matching import description_key, is_to_order, name_similarity
from ..model import Document
from ..reference import INCOTERMS_2020, normalize_port
from .base import Context, Evidence, Hit, Severity, ev, rule

T = TypeVar("T")


def _disagree(values: list[tuple[Document, T]], same: Callable[[T, T], bool]) -> bool:
    return any(not same(values[0][1], other) for _, other in values[1:])


def _collect(docs: Iterable[Document], get: Callable[[Document], T | None]):
    return [(doc, value) for doc in docs if (value := get(doc)) not in (None, "", [])]


def _within_pct(pct: float) -> Callable[[float, float], bool]:
    def same(a: float, b: float) -> bool:
        return abs(a - b) <= max(abs(a), abs(b)) * pct / 100

    return same


def _names_match(ctx: Context) -> Callable[[str, str], bool]:
    return lambda a, b: name_similarity(a, b) >= ctx.config.name_similarity


@rule("TC101", "Seller/exporter differs between documents", Severity.WARNING)
def seller_consistent(ctx: Context):
    """The seller on the invoice, packing list and certificate of origin should
    be the same company. The B/L is excluded on purpose: UCP 600 Art. 14(k)
    allows the shipper on a transport document to be a third party."""
    docs = ctx.of("commercial_invoice", "packing_list", "certificate_of_origin")
    values = _collect(docs, lambda d: d.shipper)
    if len(values) > 1 and _disagree(values, _names_match(ctx)):
        yield Hit(
            "seller named differently: " + " / ".join(f"'{v}'" for _, v in values),
            [ev(d, "shipper") for d, _ in values],
        )


@rule("TC102", "Buyer/consignee differs between documents", Severity.WARNING)
def buyer_consistent(ctx: Context):
    """The buyer should be the same party everywhere. For a "to order" B/L the
    consignee is a bank or blank, so the notify party is compared instead."""
    docs = ctx.of("commercial_invoice", "packing_list", "certificate_of_origin", "bill_of_lading")

    def party(doc: Document) -> str | None:
        if doc.doc_type == "bill_of_lading" and is_to_order(doc.consignee):
            return doc.notify_party
        return doc.consignee

    values = _collect(docs, party)
    if len(values) > 1 and _disagree(values, _names_match(ctx)):
        yield Hit(
            "buyer named differently: " + " / ".join(f"'{v}'" for _, v in values),
            [
                ev(d, "notify_party" if d.doc_type == "bill_of_lading"
                   and is_to_order(d.consignee) else "consignee")
                for d, _ in values
            ],
        )


def _quantity_rule(field: str, unit: str, ctx: Context, doc_types: tuple[str, ...]):
    values = _collect(ctx.of(*doc_types), lambda d: getattr(d, f"{field}_kg"))
    if len(values) > 1 and _disagree(values, _within_pct(ctx.config.weight_tolerance_pct)):
        shown = ", ".join(f"{d.label}: {v:,.2f} {unit}" for d, v in values)
        yield Hit(f"{field.replace('_', ' ')} differs ({shown})", [ev(d, field) for d, _ in values])


@rule("TC103", "Gross weight differs between documents", Severity.ERROR)
def gross_weight_consistent(ctx: Context):
    """Gross weight on the packing list, B/L, invoice and certificate of origin
    must agree (after unit conversion, within the configured tolerance)."""
    yield from _quantity_rule(
        "gross_weight", "kg", ctx,
        ("packing_list", "bill_of_lading", "commercial_invoice", "certificate_of_origin"),
    )


@rule("TC104", "Net weight differs between documents", Severity.WARNING)
def net_weight_consistent(ctx: Context):
    """Net weight on the packing list, invoice and certificate of origin should agree."""
    yield from _quantity_rule(
        "net_weight", "kg", ctx,
        ("packing_list", "commercial_invoice", "certificate_of_origin"),
    )


@rule("TC105", "Package count differs between documents", Severity.ERROR)
def package_count_consistent(ctx: Context):
    """The number of packages (cartons, pallets...) must be identical on every document."""
    values = _collect(ctx.documents, lambda d: d.packages)
    if len(values) > 1 and _disagree(values, lambda a, b: a == b):
        shown = ", ".join(f"{d.label}: {v}" for d, v in values)
        yield Hit(f"package count differs ({shown})", [ev(d, "packages") for d, _ in values])


@rule("TC106", "Container numbers differ between documents", Severity.ERROR)
def containers_consistent(ctx: Context):
    """Every document that lists containers must list the same ones."""
    values = _collect(ctx.documents, lambda d: frozenset(d.containers) or None)
    if len(values) < 2:
        return
    union = frozenset().union(*(v for _, v in values))
    for doc, containers in values:
        missing = sorted(union - containers)
        if missing:
            yield Hit(
                f"{doc.label} does not list {', '.join(missing)}",
                [ev(doc, "containers", ", ".join(sorted(containers)))],
            )


@rule("TC107", "Port of loading or discharge differs", Severity.ERROR)
def ports_consistent(ctx: Context):
    """Ports are compared by UN/LOCODE where known, so "Chittagong" and
    "Chattogram, BD" match. Generic credit terms like "any port in
    Bangladesh" are skipped."""
    docs = ctx.of("bill_of_lading", "commercial_invoice", "packing_list", "letter_of_credit")
    for field in ("port_of_loading", "port_of_discharge"):
        def port(doc: Document, field: str = field) -> str | None:
            value = getattr(doc, field) or ""
            return None if "any " in value.lower() else normalize_port(value)

        values = _collect(docs, port)
        if len(values) > 1 and _disagree(values, lambda a, b: a == b):
            shown = " / ".join(f"'{getattr(d, field)}'" for d, _ in values)
            yield Hit(f"{field.replace('_', ' ')} differs: {shown}", [ev(d, field) for d, _ in values])


@rule("TC108", "Country of origin differs", Severity.ERROR)
def origin_consistent(ctx: Context):
    """The origin declared on the invoice must match the certificate of origin,
    or preferential duty rates will be refused."""
    def country(value: str | None) -> str | None:
        return description_key(value).replace("made in ", "") or None

    values = []
    for doc in ctx.of("commercial_invoice", "certificate_of_origin"):
        origins = {country(i.origin) for i in doc.items if i.origin} | {country(doc.country_of_origin)}
        origins.discard(None)
        if origins:
            values.append((doc, frozenset(origins)))
    if len(values) > 1 and _disagree(values, lambda a, b: a == b):
        shown = " / ".join(f"{d.label}: {', '.join(sorted(v))}" for d, v in values)
        yield Hit(f"origin differs ({shown})", [ev(d, "country_of_origin") for d, _ in values])


@rule("TC109", "HS codes differ between invoice and certificate of origin", Severity.WARNING,
      "WCO Harmonized System")
def hs_codes_consistent(ctx: Context):
    """HS codes are compared at the 6-digit international level, since the
    remaining digits are national and legitimately differ between countries."""
    values = _collect(
        ctx.of("commercial_invoice", "certificate_of_origin", "packing_list"),
        lambda d: frozenset(i.hs_code[:6] for i in d.items if i.hs_code) or None,
    )
    if len(values) > 1 and _disagree(values, lambda a, b: a == b):
        shown = " / ".join(f"{d.label}: {', '.join(sorted(v))}" for d, v in values)
        yield Hit(f"HS codes differ ({shown})", [ev(d, "hs_code", ", ".join(sorted(v)))
                                                 for d, v in values])


@rule("TC110", "Item quantities differ between invoice and packing list", Severity.ERROR)
def item_quantities_consistent(ctx: Context):
    """Each invoiced item must be packed in the same quantity. Items are
    matched by HS code, then by description."""
    invoice, packing = ctx.first("commercial_invoice"), ctx.first("packing_list")
    if not invoice or not packing:
        return

    by_hs = all(i.hs_code for i in invoice.items + packing.items)

    def key(item):
        return item.hs_code if by_hs else description_key(item.description)

    def totals(doc):
        out = Counter()
        for item in doc.items:
            if item.quantity is not None:
                out[key(item)] += item.quantity
        return out

    inv, pack = totals(invoice), totals(packing)
    if not inv or not pack:
        return
    names = {key(i): i.description or key(i) for i in invoice.items + packing.items}
    for k in sorted(set(inv) | set(pack)):
        if abs(inv.get(k, 0) - pack.get(k, 0)) > 1e-9:
            yield Hit(
                f"{names[k]}: invoiced {inv.get(k, 0):g}, packed {pack.get(k, 0):g}",
                [Evidence(invoice.label, "quantity", f"{inv.get(k, 0):g}"),
                 Evidence(packing.label, "quantity", f"{pack.get(k, 0):g}")],
            )


@rule("TC111", "Incoterm differs between documents", Severity.ERROR)
def incoterm_consistent(ctx: Context):
    """The invoice, packing list and credit must state the same delivery term."""
    values = _collect(ctx.documents, lambda d: d.incoterm)
    if len(values) > 1 and _disagree(values, lambda a, b: a == b):
        shown = ", ".join(f"{d.label}: {v}" for d, v in values)
        yield Hit(f"Incoterm differs ({shown})", [ev(d, "incoterm") for d, _ in values])


@rule("TC112", "Freight terms contradict the Incoterm", Severity.WARNING, "Incoterms 2020")
def freight_terms_match_incoterm(ctx: Context):
    """Under E/F terms the buyer pays main carriage (B/L "freight collect");
    under C/D terms the seller does ("freight prepaid")."""
    term_doc = ctx.first("commercial_invoice") or ctx.first("letter_of_credit")
    if not term_doc or term_doc.incoterm not in INCOTERMS_2020:
        return
    expected = INCOTERMS_2020[term_doc.incoterm]
    for bl in ctx.of("bill_of_lading"):
        if bl.freight_terms and bl.freight_terms != expected:
            yield Hit(
                f"B/L says freight {bl.freight_terms} but {term_doc.incoterm} implies "
                f"freight {expected}",
                [ev(bl, "freight_terms"), ev(term_doc, "incoterm")],
            )
