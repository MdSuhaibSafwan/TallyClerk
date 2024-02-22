"""Trade reference data: Incoterms 2020 and common port identifiers."""

from __future__ import annotations

import re

# Incoterms 2020 and who normally pays main carriage, which should agree with
# the "freight prepaid / freight collect" notation on the bill of lading.
INCOTERMS_2020 = {
    "EXW": "collect", "FCA": "collect", "FAS": "collect", "FOB": "collect",
    "CPT": "prepaid", "CIP": "prepaid", "CFR": "prepaid", "CIF": "prepaid",
    "DAP": "prepaid", "DPU": "prepaid", "DDP": "prepaid",
}
SEA_ONLY_INCOTERMS = {"FAS", "FOB", "CFR", "CIF"}
CONTAINER_EQUIVALENT = {"FAS": "FCA", "FOB": "FCA", "CFR": "CPT", "CIF": "CIP"}
RETIRED_INCOTERMS = {
    "DAT": "replaced by DPU in Incoterms 2020",
    "DDU": "withdrawn in Incoterms 2010 (use DAP)",
    "DAF": "withdrawn in Incoterms 2010 (use DAP)",
    "DES": "withdrawn in Incoterms 2010 (use DAP)",
    "DEQ": "withdrawn in Incoterms 2010 (use DAT/DPU)",
    "C&F": "written as CFR since Incoterms 1990",
    "CNF": "written as CFR since Incoterms 1990",
}

# A small UN/LOCODE alias table covering major container ports, so that
# "Chittagong", "Chattogram, Bangladesh" and "BDCGP" compare equal.
PORT_ALIASES = {
    "BDCGP": ["chittagong", "chattogram"],
    "BDMGL": ["mongla"],
    "CNSHA": ["shanghai"],
    "CNNGB": ["ningbo"],
    "CNSZX": ["shenzhen"],
    "CNYTN": ["yantian"],
    "SGSIN": ["singapore"],
    "KRPUS": ["busan", "pusan"],
    "AEJEA": ["jebel ali"],
    "INNSA": ["nhava sheva", "jawaharlal nehru", "jnpt"],
    "LKCMB": ["colombo"],
    "TRMER": ["mersin"],
    "TRAMR": ["ambarli"],
    "TRIST": ["istanbul"],
    "TRIZM": ["izmir"],
    "DEHAM": ["hamburg"],
    "DEBRV": ["bremerhaven"],
    "NLRTM": ["rotterdam"],
    "BEANR": ["antwerp", "antwerpen"],
    "GBFXT": ["felixstowe"],
    "FRLEH": ["le havre"],
    "ESVLC": ["valencia"],
    "ITGOA": ["genoa", "genova"],
    "USLAX": ["los angeles"],
    "USLGB": ["long beach"],
    "USNYC": ["new york"],
    "USSAV": ["savannah"],
}
_PORT_LOOKUP = {alias: code for code, names in PORT_ALIASES.items() for alias in names}
_LOCODE = re.compile(r"\b([A-Z]{2}\s?[A-Z2-9]{3})\b")


def normalize_port(value: str | None) -> str | None:
    """Map a free-text port to its UN/LOCODE when known, else a cleaned name."""
    if not value:
        return None
    text = str(value).strip()
    code = _LOCODE.search(text)
    if code and code.group(1).replace(" ", "") in PORT_ALIASES:
        return code.group(1).replace(" ", "")
    lowered = re.sub(r"[^a-z ]", " ", text.lower())
    for alias, locode in _PORT_LOOKUP.items():
        if re.search(rf"\b{alias}\b", lowered):
            return locode
    lowered = re.sub(r"\b(port|of|seaport|harbour|harbor|any|main)\b", " ", lowered)
    return " ".join(lowered.split()) or None


def normalize_incoterm(value: str | None) -> tuple[str | None, str | None]:
    """Split ``"FOB Chattogram Incoterms 2020"`` into ``("FOB", "Chattogram")``."""
    if not value:
        return None, None
    text = re.sub(r"\(?\s*incoterms?\s*(?:®\s*)?\d{4}\s*\)?", "", str(value), flags=re.I).strip()
    match = re.match(r"([A-Za-z&]{3})\b[\s,]*(.*)", text)
    if not match:
        return None, None
    return match.group(1).upper(), (match.group(2).strip(" ,") or None)
