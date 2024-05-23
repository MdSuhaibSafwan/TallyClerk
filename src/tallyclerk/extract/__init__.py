"""Turn raw documents (text, PDF) into the dicts :mod:`tallyclerk.loader` accepts."""

from .llm import ExtractionError, LLMExtractor
from .text import read_text

__all__ = ["LLMExtractor", "ExtractionError", "read_text"]
