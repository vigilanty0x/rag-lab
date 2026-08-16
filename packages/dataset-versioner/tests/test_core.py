import math
import unittest

from dataset_versioner.core import diff, snapshot


class DatasetVersionerTests(unittest.TestCase):
    def test_stable_canonical_snapshot(self):
        self.assertEqual(snapshot([{"id": 1, "x": 2}])["version"], snapshot([{"x": 2, "id": 1}])["version"])

    def test_diff_evidence(self):
        result = diff([{"id": 1, "x": 1}, {"id": 2}], [{"id": 1, "x": 2}, {"id": 3}])
        self.assertEqual(result["added"], ["3"])
        self.assertEqual(result["removed"], ["2"])
        self.assertEqual(result["changed"], ["1"])

    def test_duplicate_and_string_collision_are_rejected(self):
        for rows in ([{"id": 1}, {"id": 1}], [{"id": 1}, {"id": "1"}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                snapshot(rows)

    def test_rejects_non_json_shapes_bool_ids_and_non_finite_values(self):
        for rows in ("bad", ["bad"], [{"id": True}], [{"id": "x", "value": math.inf}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                snapshot(rows)

    def test_id_field_is_bounded_string(self):
        with self.assertRaises(ValueError):
            snapshot([{"id": 1}], id_field=True)


if __name__ == "__main__":
    unittest.main()
