#!/usr/bin/env bash
# Extract fields from a raw B/L with a self-hosted model, then cross-check it
# against the structured documents. Nothing leaves your network.
set -euo pipefail

# 1. Serve an instruction-tuned model with an OpenAI-compatible API, e.g.:
#      vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000
#    (SGLang: python -m sglang.launch_server --model-path ... --port 8000)
export TALLYCLERK_BASE_URL="${TALLYCLERK_BASE_URL:-http://localhost:8000/v1}"
export TALLYCLERK_MODEL="${TALLYCLERK_MODEL:-Qwen/Qwen2.5-7B-Instruct}"

HERE="$(cd "$(dirname "$0")" && pwd)"
SAMPLES="$HERE/../src/tallyclerk/samples/clean"

# 2. Inspect what the model read (optional; useful for reviewing extraction)
tallyclerk extract "$HERE/bill_of_lading.txt" --doc-type bill_of_lading

# 3. Check the raw B/L together with the other documents
tallyclerk check "$HERE/bill_of_lading.txt" \
  "$SAMPLES/01_commercial_invoice.json" \
  "$SAMPLES/02_packing_list.json" \
  "$SAMPLES/05_letter_of_credit.json"
