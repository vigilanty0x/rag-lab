from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from scripts.build_release_evidence import ReleaseEvidenceError, build_release_evidence


class ReleaseEvidenceTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        (root / "pyproject.toml").write_text(
            '[project]\nname = "rag-quality-bench"\nversion = "0.3.0"\n',
            encoding="utf-8",
        )
        dist = root / "dist"
        dist.mkdir()
        (dist / "rag_quality_bench-0.3.0-py3-none-any.whl").write_bytes(b"wheel")
        (dist / "rag_quality_bench-0.3.0.tar.gz").write_bytes(b"sdist")
        return dist, root / "release-evidence"

    def test_prepared_receipt_never_claims_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist, output = self._fixture(root)
            receipt = build_release_evidence(root, dist, output)
            self.assertEqual(receipt["product"], "RAG Lab")
            self.assertEqual(receipt["version"], "0.3.0")
            self.assertEqual(receipt["state"], "PREPARED")
            self.assertFalse(receipt["signed"])
            self.assertFalse(receipt["attested"])
            self.assertFalse(receipt["tagged"])
            self.assertFalse(receipt["published"])
            self.assertFalse(receipt["released"])
            self.assertEqual(len(receipt["artifacts"]), 2)
            self.assertTrue((output / "SHA256SUMS.txt").is_file())
            self.assertTrue((output / "rag-lab.cdx.json").is_file())
            self.assertTrue((output / "RELEASE_EVIDENCE.json").is_file())
            sbom = json.loads((output / "rag-lab.cdx.json").read_text(encoding="utf-8"))
            self.assertEqual(sbom["bomFormat"], "CycloneDX")
            self.assertEqual(sbom["specVersion"], "1.6")

    def test_ambiguous_artifacts_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist, output = self._fixture(root)
            (dist / "extra.whl").write_bytes(b"extra")
            with self.assertRaisesRegex(ReleaseEvidenceError, "exactly one wheel"):
                build_release_evidence(root, dist, output)

    def test_wrong_distribution_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist, output = self._fixture(root)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "wrong"\nversion = "0.3.0"\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(ReleaseEvidenceError, "unexpected distribution"):
                build_release_evidence(root, dist, output)


if __name__ == "__main__":
    unittest.main()
