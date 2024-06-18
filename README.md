# TallyClerk

[![CI](https://github.com/MdSuhaibSafwan/tallyclerk/actions/workflows/ci.yml/badge.svg)](https://github.com/MdSuhaibSafwan/tallyclerk/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**TallyClerk checks trade documents against each other for discrepancies.** Give it a
commercial invoice, packing list, bill of lading, certificate of origin and letter of
credit, and it finds where they disagree before a bank, a customs officer or a
carrier finds it for you.

> A *tally clerk* is the dock worker who checks cargo against the paperwork. This
> project does the paperwork half.

## Why this matters

International trade runs on documents that are prepared by different parties
(exporter, freight forwarder, carrier, chamber of commerce, bank) and are required
to agree with each other. When they don't:

- **Letters of credit are refused.** Under ICC **UCP 600**, a bank pays only against
  documents that comply with the credit and are consistent with each other. Industry
  surveys have long reported that most first presentations contain at least one
  discrepancy, which leads to refusal fees, delayed payment, or the exporter losing
  the protection of the credit.
- **Cargo is held at customs.** An invoice whose origin or HS code disagrees with the
  certificate of origin loses preferential duty rates or triggers an inspection, while
  storage and demurrage keep accruing.
- **Containers are misrouted.** A single wrong digit in a container number means the
  cargo doesn't match the carrier's records.

This checking is still largely done **by hand**, by document checkers in banks,
freight forwarders and export houses, comparing PDFs side by side. TallyClerk
automates the comparison.

## What it checks

| Rule | Check | Basis |
|---|---|---|
| `TC002` | Container numbers have a valid check digit | ISO 6346 |
| `TC003` | Invoice lines = qty × price; lines sum to the total | |
| `TC004` | Net weight never exceeds gross weight | |
| `TC005` | Incoterm is valid, and outdated terms are explained (e.g. DAT → DPU) | Incoterms 2020 |
| `TC006` | HS codes are well-formed | WCO HS |
| `TC007` | FOB/CFR/CIF used for container cargo (FCA/CPT/CIP recommended) | ICC guidance |
| `TC101`–`TC102` | Seller and buyer are the same company on every document, with fuzzy matching | UCP 600 Art. 14(k) |
| `TC103`–`TC105` | Gross weight, net weight and package count agree, after unit conversion | |
| `TC106` | Every document lists the same containers | |
| `TC107` | Ports of loading/discharge agree, compared by UN/LOCODE | |
| `TC108`–`TC109` | Country of origin and HS codes agree between invoice and certificate of origin | |
| `TC110` | Invoiced quantities match packed quantities, item by item | |
| `TC111`–`TC112` | Incoterm agrees across documents and matches the B/L freight terms | Incoterms 2020 |
| `TC201` | Invoice issued by the beneficiary to the applicant | UCP 600 Art. 18(a) |
| `TC202`–`TC203` | Invoice currency and amount are within the credit, including the 39A tolerance | UCP 600 Art. 18, 30 |
| `TC204` | Shipped on or before the latest shipment date | UCP 600 Art. 20; MT700 44C |
| `TC205` | Presented within the presentation period and before expiry | UCP 600 Art. 6(e), 14(c) |

Run `tallyclerk rules` for the full list with explanations.

### Real-world variation it handles

The documents in a real shipment rarely say the same thing in the same way.
TallyClerk normalizes values before comparing them, so these **do not** raise false
alarms:

| Document A | Document B | |
|---|---|---|
| `8,064.00 KGS` | `17,778 LBS` | units converted; configurable tolerance |
| `Nordwind Textil GmbH` | `NORDWIND TEXTIL G.M.B.H., SPEICHERSTADT 7` | legal form and address ignored |
| `Anadolu Tekstil San. ve Tic. A.Ş.` | `ANADOLU TEKSTIL SANAYI VE TICARET AS` | Turkish legal forms, diacritics |
| `Chittagong` | `CHATTOGRAM, BANGLADESH (BDCGP)` | compared by UN/LOCODE |
| `FOB Chittagong, Incoterms 2020` | `FOB CHATTOGRAM` | term and place separated |
| `06 MAR 2026` | `260306` (SWIFT MT700) | common date formats |
| `1.234,56` | `1,234.56` | European and English number formats |
| B/L consignee `TO THE ORDER OF … BANK` | invoice buyer | compares the B/L **notify party** instead |
| B/L shipper is a forwarder | invoice seller | allowed by UCP 600 Art. 14(k), so not flagged |

## Quickstart

```bash
git clone https://github.com/MdSuhaibSafwan/tallyclerk
cd tallyclerk
pip install -e ".[dev]"

tallyclerk demo clean        # a compliant shipment
tallyclerk demo              # the same shipment with planted errors
```

The bundled sample is a knitwear shipment from Chattogram to Hamburg under a letter
of credit (all companies are fictional). The discrepant version produces:

| | Rule | Finding | Reference |
|---|---|---|---|
| 🔴 | `TC002` | **Invalid container number**<br>MSCU4819371 on Bill of Lading KSL-CGP-HAM-260311: check digit is 1, expected 0 | ISO 6346 |
| 🔴 | `TC003` | **Invoice arithmetic does not add up**<br>line 2 (Men's cotton pique polo shirt, knitted): 9600 x 4.60 = 44,160.00, but the line says 44,610.00 | |
| 🔴 | `TC103` | **Gross weight differs between documents**<br>Commercial Invoice: 8,064.00 kg, Packing List: 7,984.80 kg, Bill of Lading: 8,640.00 kg, Certificate of Origin: 8,064.00 kg | |
| 🔴 | `TC110` | **Item quantities differ between invoice and packing list**<br>Men's cotton pique polo shirt, knitted: invoiced 9600, packed 9360 | |
| 🔴 | `TC203` | **Invoice amount exceeds the credit**<br>invoice total 96,210.00 exceeds the credit maximum 96,000.00 (96,000.00 +0%) | UCP 600 Art. 18(b), 30 |
| 🔴 | `TC204` | **Shipped after the latest shipment date**<br>shipped 2026-03-12, 2 day(s) after the latest shipment date 2026-03-10 | UCP 600 Art. 20(a)(ii) |
| 🔴 | `TC205` | **Documents presented too late**<br>presented 25 days after shipment on 2026-03-12; the credit allows 21 | UCP 600 Art. 14(c) |
| 🟡 | `TC109` | **HS codes differ between invoice and certificate of origin**<br>Invoice: 610510, 610910 / Certificate of Origin: 610610, 610910 | WCO HS |
| 🟡 | `TC112` | **Freight terms contradict the Incoterm**<br>B/L says freight prepaid but FOB implies freight collect | Incoterms 2020 |
| … | | *16 findings in total* | |

## Checking your own documents

### Structured input (JSON)

If your documents already come from an OCR/IDP system, write one JSON object per
document. Field names are matched loosely (`seller`, `exporter` and `shipper` are all
accepted) and values can be written as they appear on the document:

```json
{
  "doc_type": "bill_of_lading",
  "bl_number": "KSL-CGP-HAM-260311",
  "shipper": "MEGHNA KNIT COMPOSITE LTD.",
  "consignee": "TO THE ORDER OF HANSEATIC HANDELSBANK AG",
  "notify_party": "NORDWIND TEXTIL G.M.B.H.",
  "port_of_loading": "CHATTOGRAM, BANGLADESH",
  "shipped_on_board": "06 MAR 2026",
  "containers": "MSCU4819209, MSCU4819370",
  "packages": "880 CARTONS",
  "gross_weight": "17,778 LBS",
  "freight_terms": "FREIGHT COLLECT"
}
```

```bash
tallyclerk check shipment-0417/                       # a folder of documents
tallyclerk check *.json --presented-on 2026-03-16     # LC presentation date
tallyclerk check shipment/ -f json -o report.json     # machine-readable
tallyclerk check shipment/ -f markdown                # for a ticket or PR comment
tallyclerk check shipment/ --ignore TC007 --weight-tolerance 1.0
```

Exit status is `1` when anything at `--fail-on` severity (default `error`) is found,
so TallyClerk can gate an automated pipeline.

### Raw documents (PDF / text), using an LLM

For PDFs and text, TallyClerk uses an LLM **only to read** the document into the
fields above. Every decision about whether documents agree is made by the
deterministic rules, so each finding can be explained and audited.

Any OpenAI-compatible endpoint works. Trade documents contain commercial terms many
companies won't send to a third-party API, so self-hosting with **vLLM** or
**SGLang** is supported directly:

```bash
pip install -e ".[pdf]"
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000

export TALLYCLERK_BASE_URL=http://localhost:8000/v1
export TALLYCLERK_MODEL=Qwen/Qwen2.5-7B-Instruct

tallyclerk extract bl.pdf                              # inspect what the model read
tallyclerk check invoice.pdf packing_list.pdf bl.pdf lc.json
```

See [`examples/run_with_vllm.sh`](examples/run_with_vllm.sh).

## Python API and custom rules

```python
from tallyclerk import Config, check, load_json

docs = load_json("invoice.json") + load_json("bl.json")
report = check(docs, Config(weight_tolerance_pct=1.0), ignore=["TC007"])

print(report.verdict)                      # CLEAN | REVIEW | DISCREPANT
for f in report.findings:
    print(f.rule_id, f.severity, f.message)
```

Company-specific policies are just functions:

```python
from tallyclerk import Severity, rule
from tallyclerk.rules import Hit
from tallyclerk.rules.base import ev

@rule("X001", "Port on the internal restricted list", Severity.ERROR, "Compliance policy 4.2")
def restricted_port(ctx):
    for doc in ctx.documents:
        if "bandar abbas" in (doc.port_of_discharge or "").lower():
            yield Hit(f"{doc.label}: {doc.port_of_discharge}", [ev(doc, "port_of_discharge")])
```

See [`examples/custom_rule.py`](examples/custom_rule.py).

## Design

```
 PDF / text ──► LLM extractor ──┐        (OpenAI, vLLM, SGLang, TRT-LLM)
                                ├──► loader ──► normalized Documents ──► rules ──► Report
 IDP / OCR JSON ────────────────┘   (aliases, units,                  (TC0xx single-doc,  (console,
                                     dates, money)                     TC1xx cross-doc,    JSON,
                                                                       TC2xx UCP 600)      Markdown)
```

- `parsing.py`: numbers, weights, money, dates, LC tolerances, ISO 6346 check digits
- `matching.py`: party-name similarity (legal forms, addresses, diacritics)
- `reference.py`: Incoterms 2020 and UN/LOCODE port aliases
- `loader.py`: raw dict → `Document`; values it can't read become `TC001` findings
  rather than being silently dropped
- `rules/`: one generator function per rule, registered with `@rule`
- `extract/`: PDF text layer and the LLM field extractor

## Development

```bash
pip install -e ".[dev,pdf]"
pytest
ruff check src tests
```

## Roadmap

- Goods-description matching between invoice and credit (UCP 600 Art. 18(c)) using embeddings
- Insurance documents (Art. 28) and air waybills (Art. 23)
- Field-level provenance (page and bounding box) from the extractor
- A small HTTP service for integration with document-management systems

## License

MIT. See [LICENSE](LICENSE).

*TallyClerk is a decision-support tool. It does not replace examination by a qualified
documentary-credit or customs specialist.*
