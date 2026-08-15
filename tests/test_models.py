import json
import unittest

from fixtures import suite_dict
from rag_quality_bench.models import BenchmarkSuite, ContractError, content_sha256


class SuiteContractTests(unittest.TestCase):
    def test_valid_suite_round_trip_and_digest(self):
        first = BenchmarkSuite.from_dict(suite_dict())
        second = BenchmarkSuite.from_json(json.dumps(first.to_dict()))
        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)

    def test_digest_ignores_mapping_order(self):
        raw = suite_dict()
        reversed_raw = dict(reversed(list(raw.items())))
        self.assertEqual(BenchmarkSuite.from_dict(raw).digest, BenchmarkSuite.from_dict(reversed_raw).digest)

    def test_unknown_suite_field_fails(self):
        raw = suite_dict()
        raw["secret_mode"] = True
        with self.assertRaisesRegex(ContractError, "unknown"):
            BenchmarkSuite.from_dict(raw)

    def test_schema_version_is_exact(self):
        raw = suite_dict()
        raw["schema_version"] = "2.0"
        with self.assertRaises(ContractError):
            BenchmarkSuite.from_dict(raw)

    def test_semver_is_required(self):
        raw = suite_dict()
        raw["version"] = "latest"
        with self.assertRaisesRegex(ContractError, "semantic"):
            BenchmarkSuite.from_dict(raw)

    def test_chunk_bounds_are_enforced(self):
        for value in (7, 501, "12"):
            raw = suite_dict()
            raw["chunk_size"] = value
            with self.assertRaises(ContractError):
                BenchmarkSuite.from_dict(raw)

    def test_overlap_must_be_smaller_than_chunk(self):
        raw = suite_dict()
        raw["chunk_overlap"] = raw["chunk_size"]
        with self.assertRaises(ContractError):
            BenchmarkSuite.from_dict(raw)

    def test_retrieval_k_is_bounded(self):
        raw = suite_dict()
        raw["retrieval_k"] = 0
        with self.assertRaises(ContractError):
            BenchmarkSuite.from_dict(raw)

    def test_duplicate_source_ids_fail(self):
        raw = suite_dict()
        raw["documents"].append(dict(raw["documents"][0]))
        with self.assertRaisesRegex(ContractError, "unique"):
            BenchmarkSuite.from_dict(raw)

    def test_duplicate_question_ids_fail(self):
        raw = suite_dict()
        raw["questions"].append(dict(raw["questions"][0]))
        with self.assertRaisesRegex(ContractError, "unique"):
            BenchmarkSuite.from_dict(raw)

    def test_unknown_expected_source_fails(self):
        raw = suite_dict()
        raw["questions"][0]["expected_source_ids"] = ["missing"]
        with self.assertRaisesRegex(ContractError, "unknown expected"):
            BenchmarkSuite.from_dict(raw)

    def test_no_answer_cannot_expect_source(self):
        raw = suite_dict()
        raw["questions"][0]["no_answer"] = True
        with self.assertRaises(ContractError):
            BenchmarkSuite.from_dict(raw)

    def test_answerable_question_requires_source(self):
        raw = suite_dict()
        raw["questions"][0]["expected_source_ids"] = []
        with self.assertRaises(ContractError):
            BenchmarkSuite.from_dict(raw)

    def test_answer_requires_claim(self):
        raw = suite_dict()
        raw["questions"][0]["response"]["claims"] = []
        with self.assertRaisesRegex(ContractError, "must contain claims"):
            BenchmarkSuite.from_dict(raw)

    def test_abstention_cannot_have_claim(self):
        raw = suite_dict()
        raw["questions"][1]["response"]["claims"] = [{"text": "x", "citations": ["handbook"]}]
        with self.assertRaises(ContractError):
            BenchmarkSuite.from_dict(raw)

    def test_duplicate_claim_citations_fail(self):
        raw = suite_dict()
        raw["questions"][0]["response"]["claims"][0]["citations"] = ["handbook", "handbook"]
        with self.assertRaisesRegex(ContractError, "duplicates"):
            BenchmarkSuite.from_dict(raw)

    def test_invalid_document_hash_shape_fails_contract(self):
        raw = suite_dict()
        raw["documents"][0]["sha256"] = "bad"
        with self.assertRaisesRegex(ContractError, "SHA-256"):
            BenchmarkSuite.from_dict(raw)

    def test_content_hash_is_utf8_sha256(self):
        self.assertEqual(content_sha256("hello"), "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")

    def test_invalid_json_has_bounded_error(self):
        with self.assertRaisesRegex(ContractError, "invalid JSON"):
            BenchmarkSuite.from_json("{")

