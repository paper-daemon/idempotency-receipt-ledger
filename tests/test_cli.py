import json
import tempfile
import unittest
from pathlib import Path

from idempotency_receipt_ledger.cli import main


class CliTests(unittest.TestCase):
    def test_conflict_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d) / "x.db")
            self.assertEqual(main(["--db", db, "reserve", "--key", "k", "--fingerprint", "a"]), 0)
            self.assertEqual(main(["--db", db, "reserve", "--key", "k", "--fingerprint", "b"]), 3)

    def test_payload_file_fingerprint(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d) / "x.db"); payload = Path(d) / "p.json"; payload.write_text(json.dumps({"x": 1}))
            self.assertEqual(main(["--db", db, "reserve", "--key", "k", "--payload-file", str(payload)]), 0)

    def test_bad_argument_combination_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d) / "x.db")
            self.assertEqual(main(["--db", db, "reserve", "--key", "k", "--fingerprint", "a", "--payload-file", "x"]), 2)


if __name__ == "__main__": unittest.main()
