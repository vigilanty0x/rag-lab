import math
import unittest

from semantic_index_doctor.core import diagnose


class DiagnoseTests(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(diagnose([{"id": "a", "vector": [1, 0]}], expected_dimension=2)["status"], "healthy")

    def test_requires_nonempty_entries_and_strict_dimension(self):
        for entries, dimension in (([], 1), ([{"id": "a", "vector": [1]}], True), ([{"id": "a", "vector": [1]}], 1.0)):
            with self.subTest(entries=entries, dimension=dimension), self.assertRaises(ValueError):
                diagnose(entries, expected_dimension=dimension)

    def test_reports_dimension_duplicate_zero_and_non_finite(self):
        self.assertEqual(diagnose([{"id": "a", "vector": [1]}], expected_dimension=2)["issues"][0]["issue"], "dimension")
        self.assertTrue(diagnose([{"id": "a", "vector": [1]}, {"id": "a", "vector": [1]}], expected_dimension=1)["issues"])
        self.assertEqual(diagnose([{"id": "a", "vector": [0]}], expected_dimension=1)["status"], "blocked")
        self.assertEqual(diagnose([{"id": "a", "vector": [math.nan]}], expected_dimension=1)["issues"][0]["issue"], "non_finite")

    def test_bool_is_not_a_vector_number(self):
        result = diagnose([{"id": "a", "vector": [True]}], expected_dimension=1)
        self.assertEqual(result["issues"][0]["issue"], "non_finite")

    def test_rejects_unstructured_entries_and_ids(self):
        for entries in (["bad"], [{"id": "", "vector": [1]}], [{"id": "a", "vector": [1], "extra": 1}]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                diagnose(entries, expected_dimension=1)

    def test_safe_norm_handles_large_finite_components(self):
        result = diagnose([{"id": "a", "vector": [1e200, 1e200]}], expected_dimension=2)
        self.assertEqual(result["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
