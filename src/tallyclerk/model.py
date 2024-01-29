"""The normalized document model all rules operate on."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

DOC_TYPES = {
    "commercial_invoice": "Commercial Invoice",
    "packing_list": "Packing List",
    "bill_of_lading": "Bill of Lading",
    "certificate_of_origin": "Certificate of Origin",
    "letter_of_credit": "Letter of Credit",
}

DOC_TYPE_ALIASES = {
    "invoice": "commercial_invoice", "ci": "commercial_invoice",
    "packing": "packing_list", "pl": "packing_list",
    "bl": "bill_of_lading", "b/l": "bill_of_lading", "bol": "bill_of_lading",
    "bill_of_loading": "bill_of_lading", "sea_waybill": "bill_of_lading",
    "coo": "certificate_of_origin", "co": "certificate_of_origin",
    "origin_certificate": "certificate_of_origin",
    "lc": "letter_of_credit", "l/c": "letter_of_credit", "mt700": "letter_of_credit",
    "documentary_credit": "letter_of_credit",
}


def canonical_doc_type(value: str) -> str | None:
    key = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if key in DOC_TYPES:
        return key
    return DOC_TYPE_ALIASES.get(key)


@dataclass
class LineItem:
    description: str = ""
    hs_code: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    amount: float | None = None
    origin: str | None = None
    packages: int | None = None
    net_weight_kg: float | None = None
    gross_weight_kg: float | None = None


@dataclass
class Document:
    """One trade document, with every value normalized to comparable units.

    ``shipper`` is the selling/exporting party (seller on an invoice, shipper
    on a B/L, exporter on a certificate of origin); ``consignee`` is the
    buying/importing party. Letter-of-credit terms live in the ``lc_*``
    fields together with ``applicant`` and ``beneficiary``.
    """

    doc_type: str
    ref: str = ""
    source: str = ""
    issue_date: date | None = None

    shipper: str | None = None
    consignee: str | None = None
    notify_party: str | None = None

    currency: str | None = None
    total_amount: float | None = None
    incoterm: str | None = None
    incoterm_place: str | None = None

    port_of_loading: str | None = None
    port_of_discharge: str | None = None
    vessel: str | None = None
    freight_terms: str | None = None  # "prepaid" | "collect"
    shipped_on_board: date | None = None

    containers: list[str] = field(default_factory=list)
    packages: int | None = None
    gross_weight_kg: float | None = None
    net_weight_kg: float | None = None
    country_of_origin: str | None = None
    items: list[LineItem] = field(default_factory=list)

    applicant: str | None = None
    beneficiary: str | None = None
    lc_number: str | None = None
    lc_amount: float | None = None
    lc_tolerance_pct: tuple[float, float] | None = None
    latest_shipment: date | None = None
    expiry_date: date | None = None
    presentation_days: int | None = None
    presentation_date: date | None = None

    raw: dict = field(default_factory=dict, repr=False)
    issues: list[tuple[str, str]] = field(default_factory=list)  # (field, problem)

    @property
    def label(self) -> str:
        name = DOC_TYPES.get(self.doc_type, self.doc_type)
        return f"{name} {self.ref}".strip()

    def raw_value(self, name: str) -> str:
        """The value as written on the document, for evidence in reports."""
        value = self.raw.get(name)
        return "" if value is None else str(value)
