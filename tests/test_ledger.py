import tempfile
import unittest
from pathlib import Path

from idempotency_receipt_ledger.ledger import ReceiptLedger


class LedgerTests(unittest.TestCase):
    def make(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return ReceiptLedger(Path(tmp.name) / "receipts.db")

    def test_first_reservation_executes(self):
        d = self.make().reserve("evt-1", "abc")
        self.assertEqual(d.decision, "EXECUTE")
        self.assertEqual(d.attempt, 1)

    def test_duplicate_in_flight_skips(self):
        l = self.make(); l.reserve("evt-1", "abc")
        self.assertEqual(l.reserve("evt-1", "abc").decision, "SKIP_IN_FLIGHT")

    def test_succeeded_duplicate_skips(self):
        l = self.make(); l.reserve("evt-1", "abc"); l.finish("evt-1", "succeeded", result={"ok": True})
        self.assertEqual(l.reserve("evt-1", "abc").decision, "SKIP_SUCCEEDED")

    def test_fingerprint_conflict_is_detected(self):
        l = self.make(); l.reserve("evt-1", "abc")
        self.assertEqual(l.reserve("evt-1", "different").decision, "CONFLICT")

    def test_failed_retry_is_explicit(self):
        l = self.make(); l.reserve("evt-1", "abc"); l.finish("evt-1", "failed", error_code="timeout")
        self.assertEqual(l.reserve("evt-1", "abc").decision, "SKIP_FAILED")
        d = l.reserve("evt-1", "abc", allow_failed_retry=True)
        self.assertEqual((d.decision, d.attempt), ("RETRY", 2))

    def test_missing_finish_key_raises(self):
        with self.assertRaises(KeyError): self.make().finish("missing", "succeeded")

    def test_raw_payload_is_not_stored_by_reserve(self):
        l = self.make(); secret = "sk_test_never_store_me"; l.reserve("evt-1", "sha256-only")
        data = Path(l.path).read_bytes()
        self.assertNotIn(secret.encode(), data)

    def test_two_connections_cannot_both_execute(self):
        l1 = self.make(); l2 = ReceiptLedger(l1.path)
        a = l1.reserve("evt-1", "abc"); b = l2.reserve("evt-1", "abc")
        self.assertEqual({a.decision, b.decision}, {"EXECUTE", "SKIP_IN_FLIGHT"})


if __name__ == "__main__": unittest.main()
