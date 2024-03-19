"""Letter-of-credit examination, following ICC UCP 600.

These rules only run when a letter of credit is part of the document set.
They mirror the checks a bank's trade-finance desk makes before paying.
"""

from __future__ import annotations

from datetime import timedelta

from ..matching import name_similarity
from .base import Context, Hit, Severity, ev, rule


@rule("TC201", "Invoice parties do not match the credit", Severity.ERROR,
      "UCP 600 Art. 18(a)(i)-(ii)")
def invoice_parties(ctx: Context):
    """The commercial invoice must appear to be issued by the beneficiary and
    made out in the name of the applicant."""
    lc = ctx.first("letter_of_credit")
    if not lc:
        return
    for inv in ctx.of("commercial_invoice"):
        checks = (("shipper", inv.shipper, "beneficiary", lc.beneficiary),
                  ("consignee", inv.consignee, "applicant", lc.applicant))
        for inv_field, inv_value, lc_field, lc_value in checks:
            if inv_value and lc_value and name_similarity(inv_value, lc_value) < ctx.config.name_similarity:
                yield Hit(
                    f"invoice {inv_field} '{inv_value}' is not the credit {lc_field} '{lc_value}'",
                    [ev(inv, inv_field), ev(lc, lc_field)],
                )


@rule("TC202", "Invoice currency differs from the credit", Severity.ERROR,
      "UCP 600 Art. 18(a)(iii)")
def invoice_currency(ctx: Context):
    """The invoice must be made out in the same currency as the credit."""
    lc = ctx.first("letter_of_credit")
    if not lc or not lc.currency:
        return
    for inv in ctx.of("commercial_invoice"):
        if inv.currency and inv.currency != lc.currency:
            yield Hit(
                f"invoice is in {inv.currency}, credit is in {lc.currency}",
                [ev(inv, "currency", inv.currency), ev(lc, "currency", lc.currency)],
            )


@rule("TC203", "Invoice amount exceeds the credit", Severity.ERROR, "UCP 600 Art. 18(b), 30")
def invoice_amount(ctx: Context):
    """The invoice may not exceed the credit amount plus any tolerance stated
    in the credit (MT700 field 39A)."""
    lc = ctx.first("letter_of_credit")
    if not lc or lc.lc_amount is None:
        return
    plus = lc.lc_tolerance_pct[1] if lc.lc_tolerance_pct else 0.0
    ceiling = round(lc.lc_amount * (1 + plus / 100), 2)
    for inv in ctx.of("commercial_invoice"):
        if inv.total_amount is not None and inv.total_amount > ceiling + ctx.config.amount_tolerance:
            yield Hit(
                f"invoice total {inv.total_amount:,.2f} exceeds the credit maximum "
                f"{ceiling:,.2f} ({lc.lc_amount:,.2f} +{plus:g}%)",
                [ev(inv, "total_amount"), ev(lc, "lc_amount")],
            )


@rule("TC204", "Shipped after the latest shipment date", Severity.ERROR,
      "UCP 600 Art. 20(a)(ii); MT700 field 44C")
def late_shipment(ctx: Context):
    """The on-board date on the B/L is the date of shipment and must not be
    later than the latest shipment date in the credit."""
    lc = ctx.first("letter_of_credit")
    if not lc or not lc.latest_shipment:
        return
    for bl in ctx.of("bill_of_lading"):
        shipped = bl.shipped_on_board or bl.issue_date
        if shipped and shipped > lc.latest_shipment:
            days = (shipped - lc.latest_shipment).days
            yield Hit(
                f"shipped {shipped.isoformat()}, {days} day(s) after the latest shipment date "
                f"{lc.latest_shipment.isoformat()}",
                [ev(bl, "shipped_on_board"), ev(lc, "latest_shipment")],
            )


@rule("TC205", "Documents presented too late", Severity.ERROR, "UCP 600 Art. 6(e), 14(c)")
def late_presentation(ctx: Context):
    """Documents must be presented within the credit's presentation period
    (21 days after shipment unless stated otherwise) and before expiry.
    Needs a presentation date: --presented-on, or presentation_date on the credit."""
    lc = ctx.first("letter_of_credit")
    if not lc:
        return
    presented = ctx.config.presented_on or lc.presentation_date
    if not presented:
        return
    if lc.expiry_date and presented > lc.expiry_date:
        yield Hit(
            f"presented {presented.isoformat()}, after the credit expired on "
            f"{lc.expiry_date.isoformat()}",
            [ev(lc, "expiry_date")],
        )
    period = lc.presentation_days or ctx.config.default_presentation_days
    for bl in ctx.of("bill_of_lading"):
        shipped = bl.shipped_on_board or bl.issue_date
        if shipped and presented > shipped + timedelta(days=period):
            yield Hit(
                f"presented {(presented - shipped).days} days after shipment on "
                f"{shipped.isoformat()}; the credit allows {period}",
                [ev(bl, "shipped_on_board")],
            )
