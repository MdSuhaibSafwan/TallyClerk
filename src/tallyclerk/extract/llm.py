"""Structured field extraction with any OpenAI-compatible chat endpoint.

Works with OpenAI, and with self-hosted models served by vLLM, SGLang or
TensorRT-LLM, which matters here: shipping documents contain commercial
terms many companies will not send to a third-party API.

The model only *reads* documents. Every judgement about whether documents
agree is made by the deterministic rules, so a report can be explained and
audited line by line.
"""

from __future__ import annotations

import json
import os
import re

import httpx

from ..model import DOC_TYPES


class ExtractionError(RuntimeError):
    pass


SYSTEM_PROMPT = """You extract data from international trade documents.
Return ONE JSON object and nothing else. Use null for anything not on the document.
Copy values exactly as written, including units and currency (e.g. "12,450.50 KGS",
"USD 48,960.00"); do not convert or compute anything.

Keys:
  doc_type: one of {doc_types}
  ref: the document's own number
  issue_date
  shipper: seller / exporter / shipper / beneficiary-side company name
  consignee: buyer / importer / consignee
  notify_party
  currency, total_amount
  incoterm: delivery term with named place, e.g. "FOB Chattogram"
  port_of_loading, port_of_discharge, vessel
  freight_terms: e.g. "FREIGHT COLLECT"
  shipped_on_board: the on-board notation date
  containers: list of container numbers
  packages: number of packages/cartons
  gross_weight, net_weight
  country_of_origin
  items: list of {{description, hs_code, quantity, unit, unit_price, amount,
                   origin, packages, net_weight, gross_weight}}
  For a letter of credit also: lc_number, applicant, beneficiary, lc_amount,
  lc_tolerance (field 39A), latest_shipment (44C), expiry_date (31D),
  presentation_days (48)."""


class LLMExtractor:
    def __init__(
        self,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        timeout: float = 120.0,
        client: httpx.Client | None = None,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self.client = client or httpx.Client(timeout=timeout)

    def extract(self, text: str, doc_type_hint: str | None = None) -> dict:
        user = f"Document text:\n\n{text}"
        if doc_type_hint:
            user = f"This is a {DOC_TYPES.get(doc_type_hint, doc_type_hint)}.\n\n" + user
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system",
                 "content": SYSTEM_PROMPT.format(doc_types=", ".join(DOC_TYPES))},
                {"role": "user", "content": user},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise ExtractionError(f"extraction request failed: {exc}") from exc
        return parse_json_object(content)


def parse_json_object(content: str) -> dict:
    """Parse a JSON object from a model reply, tolerating code fences and prose."""
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end <= start:
            raise ExtractionError("model reply contains no JSON object") from None
        try:
            data = json.loads(content[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"model reply is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ExtractionError("model reply is not a JSON object")
    return data
