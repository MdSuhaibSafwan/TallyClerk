"""Build normalized :class:`Document` objects from loosely structured data.

The input is a flat JSON object per document, as produced by an IDP/OCR
pipeline or by :mod:`tallyclerk.extract.llm`. Field names are matched
through an alias table, so ``"seller"``, ``"exporter"`` and ``"shipper"``
all land in :attr:`Document.shipper`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import parsing
from .model import Document, LineItem, canonical_doc_type
from .reference import normalize_incoterm


class LoadError(ValueError):
    pass


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "ref": ("ref", "number", "document_number", "invoice_number", "invoice_no",
            "bl_number", "bl_no", "certificate_number", "packing_list_number"),
    "issue_date": ("issue_date", "date", "invoice_date", "date_of_issue"),
    "shipper": ("shipper", "seller", "exporter", "supplier"),
    "consignee": ("consignee", "buyer", "importer", "sold_to"),
    "notify_party": ("notify_party", "notify"),
    "total_amount": ("total_amount", "total", "invoice_total", "amount"),
    "currency": ("currency",),
    "incoterm": ("incoterm", "incoterms", "terms_of_delivery", "delivery_terms"),
    "port_of_loading": ("port_of_loading", "pol", "loading_port"),
    "port_of_discharge": ("port_of_discharge", "pod", "discharge_port"),
    "vessel": ("vessel", "vessel_voyage", "ocean_vessel"),
    "freight_terms": ("freight_terms", "freight", "freight_payable"),
    "shipped_on_board": ("shipped_on_board", "on_board_date", "shipped_on_board_date"),
    "containers": ("containers", "container_numbers", "container_no"),
    "packages": ("packages", "total_packages", "number_of_packages", "cartons"),
    "gross_weight": ("gross_weight", "total_gross_weight", "gross_weight_kg"),
    "net_weight": ("net_weight", "total_net_weight", "net_weight_kg"),
    "country_of_origin": ("country_of_origin", "origin"),
    "items": ("items", "line_items", "goods"),
    "applicant": ("applicant",),
    "beneficiary": ("beneficiary",),
    "lc_number": ("lc_number", "credit_number", "documentary_credit_number"),
    "lc_amount": ("lc_amount", "credit_amount"),
    "lc_tolerance": ("lc_tolerance", "amount_tolerance", "percentage_credit_amount_tolerance"),
    "latest_shipment": ("latest_shipment", "latest_date_of_shipment", "latest_shipment_date"),
    "expiry_date": ("expiry_date", "date_of_expiry", "expiry"),
    "presentation_days": ("presentation_days", "period_for_presentation"),
    "presentation_date": ("presentation_date", "presented_on"),
}

ITEM_ALIASES: dict[str, tuple[str, ...]] = {
    "description": ("description", "goods", "desc", "description_of_goods"),
    "hs_code": ("hs_code", "hs", "hts", "tariff_code", "commodity_code"),
    "quantity": ("quantity", "qty"),
    "unit": ("unit", "uom"),
    "unit_price": ("unit_price", "price"),
    "amount": ("amount", "total", "line_total", "value"),
    "origin": ("origin", "country_of_origin"),
    "packages": ("packages", "cartons", "ctns"),
    "net_weight": ("net_weight", "net_weight_kg", "nw"),
    "gross_weight": ("gross_weight", "gross_weight_kg", "gw"),
}


def _pick(data: dict, names: tuple[str, ...]) -> Any:
    lowered = {str(k).lower(): v for k, v in data.items()}
    for name in names:
        value = lowered.get(name)
        if value not in (None, "", []):
            return value
    return None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


class _Builder:
    def __init__(self, doc: Document):
        self.doc = doc

    def parse(self, name: str, value: Any, parser: Callable[[Any], Any]) -> Any:
        if value is None:
            return None
        result = parser(value)
        if result is None:
            self.doc.issues.append((name, f"could not interpret {value!r}"))
        return result


def document_from_dict(data: dict, source: str = "") -> Document:
    if not isinstance(data, dict):
        raise LoadError(f"{source or 'document'}: expected a JSON object")
    doc_type = canonical_doc_type(str(data.get("doc_type") or data.get("type") or ""))
    if doc_type is None:
        raise LoadError(
            f"{source or 'document'}: missing or unknown 'doc_type' "
            f"({data.get('doc_type') or data.get('type')!r})"
        )

    doc = Document(doc_type=doc_type, source=source)
    b = _Builder(doc)
    v = {key: _pick(data, names) for key, names in FIELD_ALIASES.items()}
    doc.raw = {key: value for key, value in v.items() if key != "items" and value is not None}

    doc.issue_date = b.parse("issue_date", v["issue_date"], parsing.parse_date)
    doc.shipper = _clean(v["shipper"])
    doc.consignee = _clean(v["consignee"])
    doc.notify_party = _clean(v["notify_party"])
    doc.applicant = _clean(v["applicant"])
    doc.beneficiary = _clean(v["beneficiary"])
    doc.lc_number = _clean(v["lc_number"])
    doc.ref = _clean(v["ref"]) or (doc.lc_number if doc_type == "letter_of_credit" else None) or ""
    doc.vessel = _clean(v["vessel"])
    doc.port_of_loading = _clean(v["port_of_loading"])
    doc.port_of_discharge = _clean(v["port_of_discharge"])
    doc.country_of_origin = _clean(v["country_of_origin"])

    if v["currency"]:
        doc.currency = str(v["currency"]).strip().upper()
    for key, attr in (("total_amount", "total_amount"), ("lc_amount", "lc_amount")):
        if v[key] is not None:
            amount, currency = parsing.parse_money(v[key])
            if amount is None:
                doc.issues.append((key, f"could not interpret {v[key]!r}"))
            setattr(doc, attr, amount)
            doc.currency = doc.currency or currency

    if v["incoterm"]:
        doc.incoterm, doc.incoterm_place = normalize_incoterm(v["incoterm"])
        if doc.incoterm is None:
            doc.issues.append(("incoterm", f"could not interpret {v['incoterm']!r}"))

    if v["freight_terms"]:
        text = str(v["freight_terms"]).lower()
        if "prepaid" in text or "pre-paid" in text:
            doc.freight_terms = "prepaid"
        elif "collect" in text:
            doc.freight_terms = "collect"
        else:
            doc.issues.append(("freight_terms", f"could not interpret {v['freight_terms']!r}"))

    doc.shipped_on_board = b.parse("shipped_on_board", v["shipped_on_board"], parsing.parse_date)
    doc.latest_shipment = b.parse("latest_shipment", v["latest_shipment"], parsing.parse_date)
    doc.expiry_date = b.parse("expiry_date", v["expiry_date"], parsing.parse_date)
    doc.presentation_date = b.parse(
        "presentation_date", v["presentation_date"], parsing.parse_date
    )
    doc.lc_tolerance_pct = b.parse("lc_tolerance", v["lc_tolerance"], parsing.parse_tolerance)
    days = b.parse("presentation_days", v["presentation_days"], parsing.parse_number)
    doc.presentation_days = int(days) if days is not None else None

    containers = v["containers"]
    if isinstance(containers, str):
        containers = [c for c in containers.replace(";", ",").split(",") if c.strip()]
    doc.containers = [parsing.normalize_container(c) for c in containers or []]

    packages = b.parse("packages", v["packages"], parsing.parse_number)
    doc.packages = int(packages) if packages is not None else None
    doc.gross_weight_kg = b.parse("gross_weight", v["gross_weight"], parsing.parse_weight_kg)
    doc.net_weight_kg = b.parse("net_weight", v["net_weight"], parsing.parse_weight_kg)

    for index, raw_item in enumerate(v["items"] or []):
        doc.items.append(_item_from_dict(raw_item, b, index))

    if doc.doc_type == "letter_of_credit" and doc.lc_amount is None:
        doc.lc_amount, doc.total_amount = doc.total_amount, None
    return doc


def _item_from_dict(data: Any, b: _Builder, index: int) -> LineItem:
    if not isinstance(data, dict):
        b.doc.issues.append((f"items[{index}]", "expected an object"))
        return LineItem()
    v = {key: _pick(data, names) for key, names in ITEM_ALIASES.items()}
    name = f"items[{index}]"
    packages = b.parse(f"{name}.packages", v["packages"], parsing.parse_number)
    return LineItem(
        description=_clean(v["description"]) or "",
        hs_code=parsing.normalize_hs(v["hs_code"]),
        quantity=b.parse(f"{name}.quantity", v["quantity"], parsing.parse_number),
        unit=_clean(v["unit"]),
        unit_price=b.parse(f"{name}.unit_price", v["unit_price"], parsing.parse_number),
        amount=b.parse(f"{name}.amount", v["amount"], parsing.parse_number),
        origin=_clean(v["origin"]),
        packages=int(packages) if packages is not None else None,
        net_weight_kg=b.parse(f"{name}.net_weight", v["net_weight"], parsing.parse_weight_kg),
        gross_weight_kg=b.parse(f"{name}.gross_weight", v["gross_weight"], parsing.parse_weight_kg),
    )


def load_json(path: str | Path) -> list[Document]:
    """Load one document, or a list of documents, from a JSON file."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LoadError(f"{path}: invalid JSON ({exc})") from exc
    records = data if isinstance(data, list) else data.get("documents", [data])
    return [document_from_dict(record, source=str(path)) for record in records]
