"""Fuzzy comparison of party names and goods descriptions.

``"Nordwind Textil GmbH"``, ``"NORDWIND TEXTIL G.M.B.H."`` and
``"Nordwind Textil GmbH, Hamburg, Germany"`` name the same company. Exact
string comparison flags all three as discrepancies, which buries real
problems under noise; this module compares the distinctive part of the name.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_LEGAL_FORMS = {
    "co", "company", "corp", "corporation", "inc", "incorporated", "ltd", "limited", "llc",
    "llp", "plc", "pvt", "private", "pte", "gmbh", "ag", "kg", "bv", "nv", "sa", "sas", "sarl",
    "srl", "spa", "ab", "as", "oy", "kft", "sp", "zoo", "bhd", "sdn", "pty", "jsc", "ooo",
    # Turkish: Anonim Şirketi, Limited Şirketi, Sanayi ve Ticaret
    "anonim", "sirketi", "şirketi", "san", "sanayi", "ve", "tic", "ticaret", "ltdsti", "sti",
    "the", "and", "&",
}
_LEGAL_JOINED = {"gmbh", "bv", "nv", "sa", "srl", "spa", "as", "ag", "plc", "llc", "pvt", "pte"}
_TO_ORDER = re.compile(r"^\s*to\s+(?:the\s+)?order\b", re.I)


def is_to_order(consignee: str | None) -> bool:
    """A "to order" bill of lading names a bank or no one, not the buyer."""
    return bool(consignee and _TO_ORDER.match(consignee))


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


def name_tokens(name: str) -> list[str]:
    """Distinctive tokens of a party name: no legal form, address or punctuation."""
    first_line = re.split(r"[\n;]", name.strip())[0]
    # "Nordwind Textil GmbH, Hamburg" -> drop trailing address after the legal form
    text = _fold(first_line)
    text = re.sub(r"\b([a-z])\.(?=[a-z]\.)", r"\1", text)  # g.m.b.h. -> gmbh.
    text = re.sub(r"\.(?=\s|$|,)", " ", text).replace(".", "")
    parts = [p for p in re.split(r"[^a-z0-9&]+", text.split(",")[0]) if p]
    tokens = [p for p in parts if p not in _LEGAL_FORMS and p not in _LEGAL_JOINED]
    return tokens or parts


def name_similarity(a: str, b: str) -> float:
    """Similarity in [0, 1] between two party names."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0
    if ta == tb:
        return 1.0
    sa, sb = set(ta), set(tb)
    jaccard = len(sa & sb) / len(sa | sb)
    sequence = SequenceMatcher(None, " ".join(sorted(sa)), " ".join(sorted(sb))).ratio()
    joined = SequenceMatcher(None, "".join(ta), "".join(tb)).ratio()
    return max(jaccard, sequence, joined)


def description_key(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(re.findall(r"[a-z0-9]+", _fold(text)))
