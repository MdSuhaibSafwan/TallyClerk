"""Run the rule set over a document set."""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Document
from .rules import RULES, Config, Context, Finding, Severity


@dataclass
class Report:
    documents: list[Document]
    findings: list[Finding]
    rules_run: list[str] = field(default_factory=list)

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity == severity)

    @property
    def worst(self) -> Severity | None:
        return max((f.severity for f in self.findings), default=None)

    @property
    def verdict(self) -> str:
        if self.count(Severity.ERROR):
            return "DISCREPANT"
        if self.count(Severity.WARNING):
            return "REVIEW"
        return "CLEAN"

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "summary": {str(s): self.count(s) for s in reversed(Severity)},
            "documents": [
                {"type": d.doc_type, "ref": d.ref, "source": d.source} for d in self.documents
            ],
            "findings": [f.to_dict() for f in self.findings],
            "rules_run": self.rules_run,
        }


def check(
    documents: list[Document],
    config: Config | None = None,
    select: list[str] | None = None,
    ignore: list[str] | None = None,
) -> Report:
    """Run every registered rule (or the ``select``ed ones) and collect findings.

    ``select`` and ``ignore`` accept rule ids or prefixes, e.g. ``"TC2"`` for
    all letter-of-credit rules.
    """
    config = config or Config()
    ctx = Context(documents=documents, config=config)

    def matches(rule_id: str, patterns: list[str] | None) -> bool:
        return any(rule_id.startswith(p.upper()) for p in patterns or [])

    findings: list[Finding] = []
    rules_run: list[str] = []
    for rule_id, rule in sorted(RULES.items()):
        if select and not matches(rule_id, select):
            continue
        if matches(rule_id, ignore):
            continue
        rules_run.append(rule_id)
        for hit in rule.func(ctx):
            findings.append(
                Finding(
                    rule_id=rule.id,
                    title=rule.title,
                    severity=hit.severity or rule.severity,
                    message=hit.message,
                    evidence=hit.evidence,
                    reference=rule.reference,
                )
            )
    findings.sort(key=lambda f: (-f.severity, f.rule_id))
    return Report(documents=documents, findings=findings, rules_run=rules_run)
