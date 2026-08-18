"""Safely extract and test one RAG Lab source distribution."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


REQUIRED_SUFFIXES = {
    "/examples/suite.json",
    "/tests/fixtures.py",
    "/requirements-build.txt",
    "/MIGRATION-0.3.md",
    "/release-policy.v1.json",
    "/docs/RELEASE.md",
    "/scripts/build_release_evidence.py",
    "/scripts/check_release_policy.py",
}


class SdistError(ValueError):
    """Source distribution is incomplete or unsafe."""


def verify_sdist(archive: Path) -> None:
    if not archive.is_file():
        raise SdistError("sdist is missing")
    with tempfile.TemporaryDirectory(prefix="rag-lab-sdist-") as temporary:
        destination = Path(temporary).resolve()
        with tarfile.open(archive, "r:gz") as bundle:
            members = bundle.getmembers()
            names = {member.name for member in members}
            missing = [suffix for suffix in REQUIRED_SUFFIXES if not any(name.endswith(suffix) for name in names)]
            if missing:
                raise SdistError(f"incomplete sdist: {missing!r}")
            for member in members:
                target = (destination / member.name).resolve()
                if member.issym() or member.islnk() or not target.is_relative_to(destination):
                    raise SdistError(f"sdist contains unsafe path: {member.name}")
            bundle.extractall(destination, members=members)
        roots = [path for path in destination.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise SdistError(f"sdist must contain one top-level directory; found {len(roots)}")
        root = roots[0]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(root / "src")
        subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=root,
            env=env,
            check=True,
        )
        subprocess.run(
            [sys.executable, "scripts/check_release_policy.py"],
            cwd=root,
            env=env,
            check=True,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    args = parser.parse_args(argv)
    try:
        verify_sdist(args.archive)
    except (OSError, SdistError, tarfile.TarError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"sdist verification: {exc}") from exc
    print(f"sdist verified: {args.archive.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
