import json
from pathlib import Path
import tempfile
import unittest

from fixtures import StepClock, suite
from rag_quality_bench.engine import BenchmarkEngine
from rag_quality_bench.models import ContractError
from rag_quality_bench.reporting import load_report, verify_report, write_report


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.report = BenchmarkEngine(suite(), clock=StepClock(1_000)).run()

    def test_report_verifies(self):
        self.assertTrue(verify_report(self.report))

    def test_atomic_write_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "report.json"
            write_report(path, self.report)
            self.assertEqual(load_report(path)["semantic_sha256"], self.report["semantic_sha256"])

    def test_tampered_report_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            write_report(path, self.report)
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["records"][0]["passed"] = False
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "verification failed"):
                load_report(path)

    def test_invalid_json_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(ContractError):
                load_report(path)

    def test_missing_report_fails(self):
        with self.assertRaisesRegex(ContractError, "does not exist"):
            load_report("/tmp/definitely-not-a-rag-quality-report.json")

    def test_directory_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ContractError, "directory"):
                write_report(directory, self.report)

