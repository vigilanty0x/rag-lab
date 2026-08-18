from __future__ import annotations

import importlib.metadata as metadata
import unittest

import rag_lab
import rag_quality_bench


class IdentityTests(unittest.TestCase):
    def test_canonical_and_legacy_namespaces_share_version(self) -> None:
        self.assertEqual(rag_lab.__version__, "0.3.0")
        self.assertEqual(rag_quality_bench.__version__, "0.3.0")
        self.assertEqual(rag_lab.__version__, rag_quality_bench.__version__)

    def test_canonical_namespace_reexports_engine_api(self) -> None:
        self.assertIs(rag_lab.BenchmarkEngine, rag_quality_bench.BenchmarkEngine)
        self.assertIs(rag_lab.BenchmarkSuite, rag_quality_bench.BenchmarkSuite)
        self.assertIs(rag_lab.ContractError, rag_quality_bench.ContractError)
        self.assertIs(rag_lab.evaluate_suite, rag_quality_bench.evaluate_suite)

    def test_distribution_version_matches_both_namespaces(self) -> None:
        version = metadata.version("rag-quality-bench")
        self.assertEqual(version, rag_lab.__version__)
        self.assertEqual(version, rag_quality_bench.__version__)


if __name__ == "__main__":
    unittest.main()
