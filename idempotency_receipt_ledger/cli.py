from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .ledger import ReceiptLedger


def fingerprint(text: str | None, file: str | None) -> str:
    if bool(text) == bool(file):
        raise ValueError("provide exactly one of --fingerprint or --payload-file")
    if file:
        return hashlib.sha256(Path(file).read_bytes()).hexdigest()
    return text or ""


def emit(data: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, sort_keys=True))
    elif isinstance(data, dict):
        print(" ".join(f"{k}={v}" for k, v in data.items()))
    else:
        print(data)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="receipt-ledger", description="SQLite receipt ledger for idempotent side-effect workflows.")
    p.add_argument("--db", default=".receipt-ledger.sqlite3")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("reserve")
    r.add_argument("--key", required=True)
    r.add_argument("--fingerprint")
    r.add_argument("--payload-file")
    r.add_argument("--allow-failed-retry", action="store_true")
    s = sub.add_parser("succeed")
    s.add_argument("--key", required=True)
    s.add_argument("--result-json")
    f = sub.add_parser("fail")
    f.add_argument("--key", required=True)
    f.add_argument("--error-code")
    g = sub.add_parser("show")
    g.add_argument("--key", required=True)
    l = sub.add_parser("list")
    l.add_argument("--limit", type=int, default=20)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    ledger = ReceiptLedger(args.db)
    try:
        if args.command == "reserve":
            fp = fingerprint(args.fingerprint, args.payload_file)
            d = ledger.reserve(args.key, fp, allow_failed_retry=args.allow_failed_retry)
            emit(d.to_dict(), args.json)
            return 3 if d.decision == "CONFLICT" else 0
        if args.command == "succeed":
            result = json.loads(args.result_json) if args.result_json else None
            emit(ledger.finish(args.key, "succeeded", result=result), args.json)
            return 0
        if args.command == "fail":
            emit(ledger.finish(args.key, "failed", error_code=args.error_code), args.json)
            return 0
        if args.command == "show":
            emit(ledger.get(args.key), args.json)
            return 0
        if args.command == "list":
            emit({"receipts": ledger.list(limit=args.limit)}, args.json)
            return 0
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
