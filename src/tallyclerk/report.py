"""Render a :class:`Report` for terminals, machines and pull-request comments."""

from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .engine import Report
from .model import DOC_TYPES
from .rules import RULES, Severity

_STYLE = {Severity.ERROR: "bold red", Severity.WARNING: "yellow", Severity.INFO: "cyan"}
_VERDICT_STYLE = {"DISCREPANT": "bold white on red", "REVIEW": "bold black on yellow",
                  "CLEAN": "bold white on green"}


def render_console(report: Report, console: Console | None = None) -> None:
    console = console or Console()

    docs = Table(title="Documents", title_justify="left", show_edge=False)
    docs.add_column("type")
    docs.add_column("ref")
    docs.add_column("source", style="dim")
    for d in report.documents:
        docs.add_row(DOC_TYPES.get(d.doc_type, d.doc_type), d.ref, d.source)
    console.print(docs)
    console.print()

    if report.findings:
        table = Table(title="Findings", title_justify="left", show_lines=True)
        table.add_column("rule", no_wrap=True)
        table.add_column("severity", no_wrap=True)
        table.add_column("finding")
        table.add_column("reference", style="dim")
        for f in report.findings:
            body = Text(f.title, style="bold")
            body.append("\n" + f.message, style="default")
            table.add_row(f.rule_id, Text(str(f.severity), style=_STYLE[f.severity]), body,
                          f.reference or "")
        console.print(table)
        console.print()

    summary = Text(f" {report.verdict} ", style=_VERDICT_STYLE[report.verdict])
    summary.append(
        f"  {report.count(Severity.ERROR)} error(s), {report.count(Severity.WARNING)} "
        f"warning(s), {report.count(Severity.INFO)} info  ·  {len(report.documents)} documents, "
        f"{len(report.rules_run)} rules"
    )
    console.print(summary)


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)


def render_markdown(report: Report) -> str:
    icon = {Severity.ERROR: "🔴", Severity.WARNING: "🟡", Severity.INFO: "🔵"}
    lines = [
        f"## TallyClerk: **{report.verdict}**",
        "",
        f"{report.count(Severity.ERROR)} error(s) · {report.count(Severity.WARNING)} warning(s) · "
        f"{report.count(Severity.INFO)} info · {len(report.documents)} documents checked",
        "",
    ]
    if report.findings:
        lines += ["| | Rule | Finding | Reference |", "|---|---|---|---|"]
        for f in report.findings:
            message = f.message.replace("|", "\\|")
            lines.append(
                f"| {icon[f.severity]} | `{f.rule_id}` | **{f.title}**<br>{message} | "
                f"{f.reference or ''} |"
            )
    else:
        lines.append("No discrepancies found.")
    return "\n".join(lines) + "\n"


def render_rules(console: Console | None = None) -> None:
    console = console or Console()
    table = Table(show_lines=True)
    table.add_column("rule", no_wrap=True)
    table.add_column("severity", no_wrap=True)
    table.add_column("check")
    table.add_column("reference", style="dim")
    for rule_id, rule in sorted(RULES.items()):
        body = Text(rule.title, style="bold")
        if rule.description:
            body.append("\n" + " ".join(rule.description.split()), style="dim")
        table.add_row(rule_id, Text(str(rule.severity), style=_STYLE[rule.severity]), body,
                      rule.reference or "")
    console.print(table)
