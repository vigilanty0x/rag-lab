import math
import unittest

from hybrid_search_playground.core import search


class SearchTests(unittest.TestCase):
    def docs(self):
        return [
            {"id": "a", "text": "red apple", "vector": [1, 0], "query_vector": [1, 0]},
            {"id": "b", "text": "blue", "vector": [0, 1], "query_vector": [1, 0]},
        ]

    def test_rank_and_component_scores(self):
        result = search("apple", self.docs())
        self.assertEqual(result[0]["id"], "a")
        self.assertIn("semantic", result[0])

    def test_linear_token_frequency_does_not_repeat_full_scans(self):
        result = search("apple apple", self.docs(), alpha=1)
        self.assertEqual(result[0]["lexical"], 0.5)

    def test_semantic_only_and_limit(self):
        self.assertEqual(search("none", self.docs(), alpha=0, limit=1)[0]["id"], "a")

    def test_rejects_missing_vectors_and_non_finite_numbers(self):
        with self.assertRaises(ValueError):
            search("x", [{"id": "x", "text": "x"}])
        docs = self.docs()
        docs[0]["vector"][0] = math.inf
        with self.assertRaises(ValueError):
            search("x", docs)

    def test_rejects_bool_limits_and_oversized_query(self):
        with self.assertRaises(ValueError):
            search("x", self.docs(), limit=True)
        with self.assertRaises(ValueError):
            search("x" * 16_385, self.docs())

    def test_rejects_duplicate_ids_and_bad_document_shape(self):
        docs = self.docs()
        docs[1]["id"] = "a"
        with self.assertRaises(ValueError):
            search("x", docs)
        with self.assertRaises(ValueError):
            search("x", [{**self.docs()[0], "extra": True}])


if __name__ == "__main__":
    unittest.main()
