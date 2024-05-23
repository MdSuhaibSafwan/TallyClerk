"""Add a company-specific rule and run it alongside the built-in ones.

    python examples/custom_rule.py
"""

from pathlib import Path

from tallyclerk import Severity, check, load_json, rule
from tallyclerk.report import render_console
from tallyclerk.rules import Hit
from tallyclerk.rules.base import ev

RESTRICTED_PORTS = {"sevastopol", "bandar abbas"}


@rule("X001", "Port on the internal restricted list", Severity.ERROR, "Compliance policy 4.2")
def restricted_port(ctx):
    """Block shipments touching ports our compliance team has restricted."""
    for doc in ctx.documents:
        for field in ("port_of_loading", "port_of_discharge"):
            port = (getattr(doc, field) or "").lower()
            if any(name in port for name in RESTRICTED_PORTS):
                yield Hit(f"{doc.label}: {getattr(doc, field)}", [ev(doc, field)])


if __name__ == "__main__":
    samples = Path(__file__).resolve().parents[1] / "src" / "tallyclerk" / "samples" / "clean"
    documents = [d for path in sorted(samples.glob("*.json")) for d in load_json(path)]
    documents[2].port_of_discharge = "Bandar Abbas"  # simulate a re-routed B/L
    render_console(check(documents))
