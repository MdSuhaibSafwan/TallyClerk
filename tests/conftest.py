from pathlib import Path

import pytest

from tallyclerk import load_json

SAMPLES = Path(__file__).resolve().parents[1] / "src" / "tallyclerk" / "samples"


def load_sample(name: str):
    docs = []
    for path in sorted((SAMPLES / name).glob("*.json")):
        docs += load_json(path)
    return docs


@pytest.fixture
def clean_docs():
    return load_sample("clean")


@pytest.fixture
def discrepant_docs():
    return load_sample("discrepant")
