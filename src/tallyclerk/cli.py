"""Command-line interface: ``tallyclerk check|extract|rules|demo``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from importlib import resources
from pathlib import Path

from rich.console import Console

from . import __version__
from .engine import Report, check
from .extract import ExtractionError, LLMExtractor, read_text
from .loader import LoadError, document_from_dict, load_json
from .model import Document
from .parsing import parse_date
from .report import render_console, render_json, render_markdown, render_rules
from .rules import Config, Severity

DOCUMENT_SUFFIXES = {".json", ".txt", ".md", ".pdf"}
SAMPLES = ("clean", "discrepant")


def _expand(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files += sorted(p for p in path.iterdir() if p.suffix.lower() in DOCUMENT_SUFFIXES)
        elif path.exists():
            files.append(path)
        else:
            raise LoadError(f"{path}: no such file or directory")
    return files


def _extractor(args: argparse.Namespace) -> LLMExtractor | None:
    model = args.model or os.environ.get("TALLYCLERK_MODEL")
    if not model:
        return None
    base_url = args.base_url or os.environ.get("TALLYCLERK_BASE_URL", "https://api.openai.com/v1")
    return LLMExtractor(model=model, base_url=base_url)


def load_documents(paths: list[str], extractor: LLMExtractor | None) -> list[Document]:
    documents: list[Document] = []
    for path in _expand(paths):
        if path.suffix.lower() == ".json":
            documents += load_json(path)
            continue
        if extractor is None:
            raise LoadError(
                f"{path}: raw documents need an extraction model; pass --model "
                "(and --base-url for a self-hosted vLLM/SGLang server), or supply JSON"
            )
        data = extractor.extract(read_text(path))
        documents.append(document_from_dict(data, source=str(path)))
    if not documents:
        raise LoadError("no documents found")
    return documents


def _emit(report: Report, fmt: str, output: str | None) -> None:
    if fmt == "console" and not output:
        render_console(report)
        return
    text = {"json": render_json, "markdown": render_markdown}.get(fmt, render_json)(report)
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _exit_code(report: Report, fail_on: str) -> int:
    if fail_on == "never" or report.worst is None:
        return 0
    return 1 if report.worst >= Severity.parse(fail_on) else 0


def _config(args: argparse.Namespace) -> Config:
    presented = None
    if args.presented_on:
        presented = parse_date(args.presented_on)
        if presented is None:
            raise LoadError(f"--presented-on: cannot read date {args.presented_on!r}")
    return Config(
        weight_tolerance_pct=args.weight_tolerance,
        name_similarity=args.name_similarity,
        presented_on=presented,
    )


def _split(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    return [part.strip() for v in values for part in v.split(",") if part.strip()]


def cmd_check(args: argparse.Namespace) -> int:
    documents = load_documents(args.paths, _extractor(args))
    report = check(documents, _config(args), select=_split(args.select), ignore=_split(args.ignore))
    _emit(report, args.format, args.output)
    return _exit_code(report, args.fail_on)


def cmd_demo(args: argparse.Namespace) -> int:
    folder = resources.files("tallyclerk") / "samples" / args.sample
    with resources.as_file(folder) as path:
        documents = load_documents([str(path)], None)
    for doc in documents:
        doc.source = f"samples/{args.sample}/{Path(doc.source).name}"
    report = check(documents, _config(args))
    _emit(report, args.format, args.output)
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    extractor = _extractor(args)
    if extractor is None:
        raise LoadError("extract needs --model (or TALLYCLERK_MODEL)")
    data = extractor.extract(read_text(args.path), doc_type_hint=args.doc_type)
    document_from_dict(data, source=args.path)  # validate before writing
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


def cmd_rules(args: argparse.Namespace) -> int:
    render_rules()
    return 0


def _add_check_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-f", "--format", choices=["console", "json", "markdown"], default="console")
    p.add_argument("-o", "--output", help="write the report to a file")
    p.add_argument("--presented-on", help="date documents are presented to the bank (LC checks)")
    p.add_argument("--weight-tolerance", type=float, default=0.5, metavar="PCT",
                   help="allowed weight difference between documents, in %% (default 0.5)")
    p.add_argument("--name-similarity", type=float, default=0.85, metavar="X",
                   help="minimum similarity for two party names to match (default 0.85)")


def _add_model_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--model", help="extraction model (env TALLYCLERK_MODEL)")
    p.add_argument("--base-url", help="OpenAI-compatible endpoint, e.g. http://localhost:8000/v1 "
                   "for vLLM (env TALLYCLERK_BASE_URL)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tallyclerk",
        description="Cross-check trade documents (invoice, packing list, B/L, certificate of "
                    "origin, letter of credit) for discrepancies.",
    )
    parser.add_argument("--version", action="version", version=f"tallyclerk {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", help="check a set of documents for discrepancies")
    p.add_argument("paths", nargs="+", help="document files or folders (.json, .pdf, .txt)")
    _add_check_options(p)
    _add_model_options(p)
    p.add_argument("--select", action="append", help="only run these rules (ids or prefixes)")
    p.add_argument("--ignore", action="append", help="skip these rules (ids or prefixes)")
    p.add_argument("--fail-on", choices=["error", "warning", "info", "never"], default="error",
                   help="exit with status 1 at this severity or worse (default: error)")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("demo", help="check a bundled sample shipment")
    p.add_argument("sample", nargs="?", choices=SAMPLES, default="discrepant")
    _add_check_options(p)
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("extract", help="extract one raw document to JSON with an LLM")
    p.add_argument("path")
    p.add_argument("-o", "--output")
    p.add_argument("--doc-type", help="hint the document type")
    _add_model_options(p)
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("rules", help="list the built-in rules")
    p.set_defaults(func=cmd_rules)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (LoadError, ExtractionError, RuntimeError, ValueError) as exc:
        Console(stderr=True).print(f"[bold red]error:[/] {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
