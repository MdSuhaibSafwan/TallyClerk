"""Rule registry and the types rules produce."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum

from ..model import Document


class Severity(IntEnum):
    INFO = 1
    WARNING = 2
    ERROR = 3

    @classmethod
    def parse(cls, value: str) -> Severity:
        try:
            return cls[value.strip().upper()]
        except KeyError:
            raise ValueError(f"unknown severity {value!r} (info, warning, error)") from None

    def __str__(self) -> str:
        return self.name.lower()


@dataclass(frozen=True)
class Evidence:
    document: str
    field: str
    value: str


@dataclass
class Hit:
    """What a rule reports; the engine turns it into a :class:`Finding`."""

    message: str
    evidence: list[Evidence] = field(default_factory=list)
    severity: Severity | None = None


@dataclass
class Finding:
    rule_id: str
    title: str
    severity: Severity
    message: str
    evidence: list[Evidence]
    reference: str | None = None

    def to_dict(self) -> dict:
        return {
            "rule": self.rule_id,
            "title": self.title,
            "severity": str(self.severity),
            "message": self.message,
            "reference": self.reference,
            "evidence": [e.__dict__ for e in self.evidence],
        }


@dataclass
class Config:
    weight_tolerance_pct: float = 0.5
    amount_tolerance: float = 0.01
    name_similarity: float = 0.85
    default_presentation_days: int = 21
    presented_on: date | None = None


@dataclass
class Context:
    documents: list[Document]
    config: Config

    def of(self, *doc_types: str) -> list[Document]:
        return [d for d in self.documents if d.doc_type in doc_types]

    def first(self, doc_type: str) -> Document | None:
        found = self.of(doc_type)
        return found[0] if found else None


RuleFunc = Callable[[Context], Iterable[Hit]]


@dataclass
class Rule:
    id: str
    title: str
    severity: Severity
    func: RuleFunc
    reference: str | None = None

    @property
    def description(self) -> str:
        return (self.func.__doc__ or "").strip()


RULES: dict[str, Rule] = {}


def rule(rule_id: str, title: str, severity: Severity, reference: str | None = None):
    """Register a rule. Rules are generators of :class:`Hit`."""

    def decorator(func: RuleFunc) -> RuleFunc:
        if rule_id in RULES:
            raise ValueError(f"duplicate rule id {rule_id}")
        RULES[rule_id] = Rule(rule_id, title, severity, func, reference)
        return func

    return decorator


def ev(doc: Document, field_name: str, value: object = None) -> Evidence:
    shown = doc.raw_value(field_name) if value is None else value
    if isinstance(shown, float):
        shown = f"{shown:,.2f}"
    return Evidence(doc.label, field_name, str(shown))
