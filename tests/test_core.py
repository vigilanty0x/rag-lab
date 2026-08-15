import hashlib
import json
import unittest

from rag_citation_explorer import evaluate

CHUNK = "The release artifact digest is abc123 and the tests passed."
DIGEST = hashlib.sha256(CHUNK.encode()).hexdigest()
GOOD = {
    "answer": "The artifact digest is abc123.",
    "claims": [{"id": "c1", "text": "artifact digest abc123"}],
    "sources": [{"source_id": "doc-1", "chunks": [{"chunk_id": "chunk-1", "text": CHUNK, "sha256": DIGEST}]}],
    "citations": [{"claim_id": "c1", "source_id": "doc-1", "chunk_id": "chunk-1", "quote": "release artifact digest is abc123", "start": 4, "end": 37}],
}


class ContractTests(unittest.TestCase):
    def test_registered_quote_conservatively_supports_claim(self):
        result = evaluate(GOOD)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["citation_view"]["structural_coverage"], 1.0)
        self.assertEqual(result["citation_view"]["semantic_support_coverage"], 1.0)

    def test_structural_citation_without_semantic_support_fails_with_view(self):
        record = {**GOOD, "claims": [{"id": "c1", "text": "deployment completed safely"}]}
        result = evaluate(record)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["citation_view"]["structural_coverage"], 1.0)
        self.assertEqual(result["citation_view"]["semantic_support_coverage"], 0.0)

    def test_quote_span_must_be_exact(self):
        citation = {**GOOD["citations"][0], "start": 0}
        self.assertEqual(evaluate({**GOOD, "citations": [citation]})["status"], "failed")

    def test_chunk_digest_must_match_registry_text(self):
        sources = [{"source_id": "doc-1", "chunks": [{"chunk_id": "chunk-1", "text": CHUNK, "sha256": "a" * 64}]}]
        self.assertEqual(evaluate({**GOOD, "sources": sources})["status"], "failed")

    def test_unknown_source_or_chunk_fails(self):
        citation = {**GOOD["citations"][0], "chunk_id": "missing"}
        self.assertEqual(evaluate({**GOOD, "citations": [citation]})["status"], "failed")

    def test_missing_citation_is_uncovered_not_verified(self):
        result = evaluate({**GOOD, "citations": []})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["citation_view"]["unsupported_claims"], ["c1"])

    def test_non_object_nonfinite_and_missing_fail_closed(self):
        self.assertEqual(evaluate(None)["status"], "failed")
        self.assertEqual(evaluate({**GOOD, "extra": float("nan")})["status"], "failed")
        self.assertEqual(evaluate({})["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
