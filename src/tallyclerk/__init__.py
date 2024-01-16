"""TallyClerk: cross-document discrepancy detection for trade paperwork."""

__version__ = "0.1.0"

from .engine import Report, check
from .loader import document_from_dict, load_json
from .model import Document, LineItem
from .rules import RULES, Config, Finding, Severity, rule

__all__ = [
    "RULES", "Config", "Document", "Finding", "LineItem", "Report", "Severity",
    "check", "document_from_dict", "load_json", "rule", "__version__",
]
