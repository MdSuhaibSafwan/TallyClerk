"""Read the text layer of a document file."""

from __future__ import annotations

from pathlib import Path


def read_text(path: str | Path) -> str:
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        return path.read_text(encoding="utf-8", errors="replace")
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "reading PDFs needs the 'pdf' extra: pip install 'tallyclerk[pdf]'"
        ) from exc
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if not text.strip():
        raise RuntimeError(f"{path}: no text layer (scanned PDF?); run OCR first")
    return text
