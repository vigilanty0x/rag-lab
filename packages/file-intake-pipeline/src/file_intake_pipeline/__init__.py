"""Fail-closed validation of synthetic file-intake manifests."""

import argparse
import hashlib
import json
import re
from pathlib import PurePosixPath

ALLOWED = {"text/plain", "application/json", "text/markdown"}
HEX64 = re.compile(r"[0-9a-f]{64}")
MAX_FILES = 1_000
MAX_BYTES = 1_000_000_000


def _safe_path(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 512 or "\\" in value
            or any(ord(c) < 32 for c in value)):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and value not in {".", ".."} and ".." not in path.parts and path.as_posix() == value


def intake(files, max_files=100, max_bytes=10_000_000):
    if (not isinstance(max_files, int) or isinstance(max_files, bool) or not 0 <= max_files <= MAX_FILES
            or not isinstance(max_bytes, int) or isinstance(max_bytes, bool)
            or not 0 <= max_bytes <= MAX_BYTES or not isinstance(files, list)
            or len(files) > max_files):
        return {"accepted": False, "errors": ["invalid_bounds_or_file_count"], "files": []}
    errors, clean, seen = [], [], set()
    total = 0
    for index, item in enumerate(files):
        if not isinstance(item, dict) or set(item) != {"name", "size", "sha256", "media_type"}:
            errors.append({"index": index, "error": "invalid_entry"})
            continue
        name, size, digest, media = (item[k] for k in ("name", "size", "sha256", "media_type"))
        if not _safe_path(name) or name in seen:
            errors.append({"index": index, "error": "invalid_or_duplicate_name"})
            continue
        seen.add(name)
        valid = True
        if not isinstance(size, int) or isinstance(size, bool) or not 0 <= size <= max_bytes:
            errors.append({"name": name, "error": "invalid_size"})
            valid = False
        if not isinstance(digest, str) or not HEX64.fullmatch(digest):
            errors.append({"name": name, "error": "invalid_sha256"})
            valid = False
        if not isinstance(media, str) or media not in ALLOWED:
            errors.append({"name": name, "error": "unsupported_media_type"})
            valid = False
        if valid:
            total += size
            clean.append(dict(item))
    if total > max_bytes:
        errors.append({"error": "aggregate_byte_limit"})
    if errors:
        return {"accepted": False, "errors": errors, "files": [], "total_bytes": total}
    clean.sort(key=lambda item: item["name"])
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"))
    return {"accepted": True, "errors": [], "files": clean, "total_bytes": total,
            "manifest_sha256": hashlib.sha256(canonical.encode()).hexdigest()}


def probe():
    good = intake([{"name": "a.txt", "size": 1, "sha256": "a" * 64, "media_type": "text/plain"}])
    bad = intake([{"name": "../x", "size": 1, "sha256": "a" * 64, "media_type": "text/plain"}])
    return {"ok": good["accepted"] and not bad["accepted"], "counter_proof": not bad["accepted"]}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("intake", "probe"))
    parser.add_argument("--input")
    args = parser.parse_args(argv)
    try:
        data = json.load(open(args.input, encoding="utf-8")) if args.input else {}
        out = probe() if args.command == "probe" else intake(data.get("files") if isinstance(data, dict) else None)
    except (OSError, UnicodeError, json.JSONDecodeError):
        out = {"accepted": False, "errors": ["input_unreadable"], "files": []}
    print(json.dumps(out, sort_keys=True))
    return 0 if out.get("ok", out.get("accepted", False)) else 2
