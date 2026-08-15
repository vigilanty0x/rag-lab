import unittest
from embedding_lab import evaluate

GOOD = {"model":"embed-small","dimensions":768,"vector_count":100}
BAD = {"model":"embed-small","dimensions":0,"vector_count":100}

class CoreTests(unittest.TestCase):
    def test_good_record_passes_deterministically(self):
        first = evaluate(GOOD)
        self.assertEqual(first["status"], "passed")
        self.assertEqual(first, evaluate(dict(reversed(list(GOOD.items())))))
        self.assertEqual(len(first["evidence_sha256"]), 64)

    def test_bad_record_fails(self):
        self.assertEqual(evaluate(BAD)["status"], "failed")

    def test_missing_field_blocks(self):
        incomplete = dict(GOOD)
        incomplete.pop(next(iter(incomplete)))
        self.assertEqual(evaluate(incomplete)["status"], "blocked")

if __name__ == "__main__":
    unittest.main()

