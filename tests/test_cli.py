import json

import httpx
from conftest import SAMPLES

from tallyclerk import cli
from tallyclerk.extract import ExtractionError, LLMExtractor
from tallyclerk.extract.llm import parse_json_object


def test_demo_runs(capsys):
    assert cli.main(["demo", "clean", "-f", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "CLEAN"


def test_check_exit_codes(capsys):
    folder = str(SAMPLES / "discrepant")
    assert cli.main(["check", folder, "-f", "json"]) == 1
    assert cli.main(["check", folder, "-f", "json", "--fail-on", "never"]) == 0
    assert cli.main(["check", str(SAMPLES / "clean"), "-f", "json"]) == 0
    assert cli.main(["check", str(SAMPLES / "clean"), "-f", "json", "--fail-on", "info"]) == 1


def test_markdown_output(tmp_path):
    out = tmp_path / "report.md"
    cli.main(["check", str(SAMPLES / "discrepant"), "-f", "markdown", "-o", str(out)])
    text = out.read_text()
    assert "DISCREPANT" in text and "`TC204`" in text


def test_raw_document_without_model_is_a_usage_error(tmp_path, monkeypatch):
    monkeypatch.delenv("TALLYCLERK_MODEL", raising=False)
    raw = tmp_path / "bl.txt"
    raw.write_text("BILL OF LADING ...")
    assert cli.main(["check", str(raw)]) == 2


def _mock_client(reply: str) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["temperature"] == 0
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_llm_extraction_feeds_the_rules(tmp_path, capsys):
    reply = '```json\n{"doc_type": "bill_of_lading", "bl_number": "X1", "gross_weight": "9,999 KGS"}\n```'
    extractor = LLMExtractor(model="local", base_url="http://vllm:8000/v1", api_key="",
                             client=_mock_client(reply))
    raw = tmp_path / "bl.txt"
    raw.write_text("BILL OF LADING X1 ... GROSS WEIGHT 9,999 KGS")
    docs = cli.load_documents([str(raw), str(SAMPLES / "clean" / "02_packing_list.json")], extractor)
    assert docs[0].gross_weight_kg == 9999.0
    from tallyclerk import check
    assert "TC103" in {f.rule_id for f in check(docs).findings}


def test_parse_json_object_tolerates_prose():
    assert parse_json_object('Here you go: {"a": 1} hope that helps') == {"a": 1}


def test_parse_json_object_rejects_non_json():
    try:
        parse_json_object("I cannot read this document.")
    except ExtractionError:
        return
    raise AssertionError("expected ExtractionError")
