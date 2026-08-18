import math
import unittest

from data_freshness_monitor.core import monitor


class FreshnessTests(unittest.TestCase):
    def test_fresh_stale_unknown_and_future_are_distinct(self):
        now = "2026-01-01T01:00:00Z"
        datasets = [
            {"id": "fresh", "observed_at": "2026-01-01T00:30:00+00:00"},
            {"id": "stale", "observed_at": "2025-12-31T22:00:00Z"},
            {"id": "unknown"},
            {"id": "future", "observed_at": "2026-01-01T02:00:00Z"},
        ]
        result = monitor(datasets, now=now)
        self.assertEqual([row["status"] for row in result["datasets"]], ["fresh", "stale", "blocked", "future"])
        self.assertEqual(result["datasets"][-1]["age_seconds"], 0.0)
        self.assertEqual(result["status"], "degraded")

    def test_requires_nonempty_datasets_and_aware_time(self):
        with self.assertRaises(ValueError):
            monitor([], now="2026-01-01T00:00:00Z")
        with self.assertRaises(ValueError):
            monitor([{"id": "x"}], now="2026-01-01T00:00:00")
        with self.assertRaises(ValueError):
            monitor([{"id": "x", "observed_at": "2026-01-01T00:00:00"}], now="2026-01-01T00:00:00Z")

    def test_limits_are_finite_nonnegative_numbers_not_bool(self):
        for value in (True, -1, math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                monitor([{"id": "x"}], now="2026-01-01T00:00:00Z", default_max_age_seconds=value)

    def test_rejects_duplicate_or_unstructured_ids(self):
        with self.assertRaises(ValueError):
            monitor([{"id": "x"}, {"id": "x"}], now="2026-01-01T00:00:00Z")
        with self.assertRaises(ValueError):
            monitor([{"id": 1}], now="2026-01-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
