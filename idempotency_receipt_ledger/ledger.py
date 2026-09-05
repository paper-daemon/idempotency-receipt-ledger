from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

VALID_STATES = {"reserved", "succeeded", "failed"}


@dataclass(frozen=True)
class Decision:
    decision: str
    key: str
    state: str
    attempt: int
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReceiptLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=10000")
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS receipts (
                  key TEXT PRIMARY KEY,
                  fingerprint TEXT NOT NULL,
                  state TEXT NOT NULL CHECK (state IN ('reserved','succeeded','failed')),
                  attempt INTEGER NOT NULL,
                  created_at REAL NOT NULL,
                  updated_at REAL NOT NULL,
                  result_json TEXT,
                  error_code TEXT
                )
                """
            )

    def reserve(self, key: str, fingerprint: str, *, allow_failed_retry: bool = False) -> Decision:
        if not key.strip() or not fingerprint.strip():
            raise ValueError("key and fingerprint must be non-empty")
        now = time.time()
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM receipts WHERE key = ?", (key,)).fetchone()
            if row is None:
                con.execute(
                    "INSERT INTO receipts(key,fingerprint,state,attempt,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (key, fingerprint, "reserved", 1, now, now),
                )
                con.commit()
                return Decision("EXECUTE", key, "reserved", 1, fingerprint)
            if row["fingerprint"] != fingerprint:
                con.rollback()
                return Decision("CONFLICT", key, row["state"], row["attempt"], row["fingerprint"])
            if row["state"] == "succeeded":
                con.rollback()
                return Decision("SKIP_SUCCEEDED", key, "succeeded", row["attempt"], fingerprint)
            if row["state"] == "reserved":
                con.rollback()
                return Decision("SKIP_IN_FLIGHT", key, "reserved", row["attempt"], fingerprint)
            if row["state"] == "failed" and allow_failed_retry:
                attempt = row["attempt"] + 1
                con.execute(
                    "UPDATE receipts SET state='reserved', attempt=?, updated_at=?, error_code=NULL WHERE key=?",
                    (attempt, now, key),
                )
                con.commit()
                return Decision("RETRY", key, "reserved", attempt, fingerprint)
            con.rollback()
            return Decision("SKIP_FAILED", key, "failed", row["attempt"], fingerprint)
        finally:
            con.close()

    def finish(self, key: str, state: str, *, result: Any = None, error_code: str | None = None) -> dict[str, Any]:
        if state not in {"succeeded", "failed"}:
            raise ValueError("finish state must be succeeded or failed")
        now = time.time()
        result_json = None if result is None else json.dumps(result, ensure_ascii=False, sort_keys=True)
        with self._connect() as con:
            cur = con.execute(
                "UPDATE receipts SET state=?, updated_at=?, result_json=?, error_code=? WHERE key=?",
                (state, now, result_json, error_code, key),
            )
            if cur.rowcount != 1:
                raise KeyError(key)
        return self.get(key)

    def get(self, key: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute("SELECT * FROM receipts WHERE key = ?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        out = dict(row)
        if out["result_json"] is not None:
            out["result"] = json.loads(out.pop("result_json"))
        else:
            out.pop("result_json")
            out["result"] = None
        return out

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        with self._connect() as con:
            rows = con.execute("SELECT * FROM receipts ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
