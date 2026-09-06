"""Generate bounded, deterministic release evidence for a RAG Lab candidate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform

import tomllib
from typing import Any


MAX_ARTIFACT_BYTES = 256 * 1024 * 1024
EXPECTED_DISTRIBUTION = "rag-quality-bench"


class ReleaseEvidenceError(ValueError):
    """Candidate artifacts or metadata are missing, ambiguous, or unsafe."""


def _sha256(path: Path) -> tuple[int, str]:
    size = path.stat().st_size
    if size > MAX_ARTIFACT_BYTES:
        raise ReleaseEvidenceError(f"artifact exceeds {MAX_ARTIFACT_BYTES} bytes: {path.name}")
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return size, digest.hexdigest()


def _project(root: Path) -> tuple[str, str]:
    try:
        value = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise ReleaseEvidenceError("cannot read project metadata") from exc
    name = value.get("name")
    version = value.get("version")
    if name != EXPECTED_DISTRIBUTION or not isinstance(version, str) or not version:
        raise ReleaseEvidenceError("unexpected distribution identity or version")
    return name, version


def _artifacts(dist: Path, version: str) -> list[Path]:
    wheel = sorted(dist.glob("*.whl"))
    sdist = sorted(dist.glob("*.tar.gz"))
    if len(wheel) != 1 or len(sdist) != 1:
        raise ReleaseEvidenceError(
            f"expected exactly one wheel and one sdist; found wheels={len(wheel)} sdists={len(sdist)}"
        )
    expected_prefix = f"rag_quality_bench-{version}"
    if not wheel[0].name.startswith(expected_prefix) or not sdist[0].name.startswith(expected_prefix.replace("_", "_")):
        # setuptools currently normalizes the sdist project name with underscores.
        raise ReleaseEvidenceError("artifact names do not match candidate version")
    return [wheel[0], sdist[0]]


def build_release_evidence(root: Path, dist: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    dist = dist.resolve()
    output.mkdir(parents=True, exist_ok=True)
    distribution, version = _project(root)
    artifacts = _artifacts(dist, version)

    rows = []
    for path in artifacts:
        size, digest = _sha256(path)
        rows.append({"name": path.name, "size": size, "sha256": digest})
    rows.sort(key=lambda item: item["name"])

    checksum_text = "".join(f"{item['sha256']}  {item['name']}\n" for item in rows)
    (output / "SHA256SUMS.txt").write_text(checksum_text, encoding="utf-8")

    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{sha256((distribution + ':' + version).encode()).hexdigest()[:8]}-0000-4000-8000-{sha256(version.encode()).hexdigest()[:12]}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "RAG Lab",
                "group": "vigilanty0x",
                "version": version,
                "purl": f"pkg:pypi/{distribution}@{version}",
                "properties": [
                    {"name": "rag-lab:distribution", "value": distribution},
                    {"name": "rag-lab:runtime-dependencies", "value": "0"},
                ],
            }
        },
        "components": [],
        "properties": [
            {"name": f"rag-lab:artifact:{item['name']}:sha256", "value": item["sha256"]}
            for item in rows
        ],
    }
    (output / "rag-lab.cdx.json").write_text(
        json.dumps(bom, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    receipt = {
        "schema_version": "1.0",
        "product": "RAG Lab",
        "repository": "vigilanty0x/rag-lab",
        "distribution": distribution,
        "version": version,
        "state": "PREPARED",
        "source_sha": os.environ.get("GITHUB_SHA") or os.environ.get("SOURCE_SHA") or "not-recorded",
        "source_ref": os.environ.get("GITHUB_REF") or "not-recorded",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "artifacts": rows,
        "checksums": "SHA256SUMS.txt",
        "sbom": "rag-lab.cdx.json",
        "tests_verified": os.environ.get("RAG_LAB_TESTS_VERIFIED") == "1",
        "counterproof_verified": os.environ.get("RAG_LAB_COUNTERPROOF_VERIFIED") == "1",
        "signed": False,
        "attested": False,
        "tagged": False,
        "published": False,
        "released": False,
    }
    (output / "RELEASE_EVIDENCE.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path, default=Path("release-evidence"))
    args = parser.parse_args(argv)
    try:
        receipt = build_release_evidence(args.root, args.dist, args.output)
    except (OSError, ReleaseEvidenceError) as exc:
        raise SystemExit(f"release evidence: {exc}") from exc
    print(
        f"release evidence prepared: product={receipt['product']} version={receipt['version']} "
        f"artifacts={len(receipt['artifacts'])} state={receipt['state']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
