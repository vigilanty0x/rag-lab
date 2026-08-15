"""Atomic report output and semantic verification."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .models import ContractError, canonical_sha256


def semantic_payload(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "suite_sha256": report.get("suite_sha256"),
        "index_sha256": report.get("index_sha256"),
        "inventory": report.get("inventory"),
        "metrics": {
            key: value
            for key, value in report.get("metrics", {}).items()
            if "latency" not in key
        },
        "records": [
            {key: value for key, value in record.items() if key != "retrieval_latency_ms"}
            for record in report.get("records", [])
        ],
    }


def verify_report(report: dict[str, Any]) -> bool:
    expected = report.get("semantic_sha256")
    return isinstance(expected, str) and expected == canonical_sha256(semantic_payload(report))


def load_report(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_file():
        raise ContractError(f"report does not exist: {target}")
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read report: {target}") from exc
    if not isinstance(raw, dict) or not verify_report(raw):
        raise ContractError("report semantic SHA verification failed")
    return raw


def write_report(path: str | Path, report: dict[str, Any]) -> None:
    target = Path(path)
    if target.exists() and target.is_dir():
        raise ContractError("report path cannot be a directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
            temporary = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    load_report(target)

