import unittest

from file_intake_pipeline import intake, probe

F = {"name": "a.txt", "size": 2, "sha256": "a" * 64, "media_type": "text/plain"}


class Tests(unittest.TestCase):
    def test_accept_and_total(self):
        result = intake([F])
        self.assertTrue(result["accepted"])
        self.assertEqual(result["total_bytes"], 2)

    def test_name_normalization_and_uniqueness(self):
        for name in ("../x", "/x", "a/../x", "a//x", "a\\x", "", "\ud800"):
            self.assertFalse(intake([{**F, "name": name}])["accepted"])
        self.assertFalse(intake([F, F])["accepted"])

    def test_strict_entries_hash_media_and_size(self):
        for item in ({**F, "size": True}, {**F, "sha256": "A" * 64},
                     {**F, "media_type": "image/png"}, {**F, "extra": 1}, "bad"):
            self.assertFalse(intake([item])["accepted"])

    def test_aggregate_bytes(self):
        other = {**F, "name": "b.txt", "size": 2}
        self.assertFalse(intake([F, other], max_bytes=3)["accepted"])

    def test_probe(self):
        self.assertTrue(probe()["ok"])


if __name__ == "__main__":
    unittest.main()
