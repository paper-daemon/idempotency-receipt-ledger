#!/usr/bin/env bash
set -euo pipefail
DB="${1:-/tmp/receipt-ledger-demo.db}"
rm -f "$DB"
python -m idempotency_receipt_ledger.cli --db "$DB" reserve --key demo:42 --fingerprint operation-v1
python -m idempotency_receipt_ledger.cli --db "$DB" succeed --key demo:42 --result-json '{"ok":true}'
python -m idempotency_receipt_ledger.cli --db "$DB" reserve --key demo:42 --fingerprint operation-v1
