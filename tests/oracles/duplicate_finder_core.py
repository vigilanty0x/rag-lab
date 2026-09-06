"""Bounded exact and normalized duplicate grouping."""

import hashlib
import json
import re

MAX_RECORDS = 100_000
MAX_FIELDS = 100
MAX_RECORD_FIELDS = 1_000
MAX_TOTAL_BYTES = 20_000_000


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("records must contain finite JSON values") from exc


def find(records, fields):
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_RECORDS:
        raise ValueError("records must be a bounded nonempty list")
    if not isinstance(fields, list) or not 1 <= len(fields) <= MAX_FIELDS:
        raise ValueError("fields must be a bounded nonempty list")
    if len(set(fields)) != len(fields) or any(not isinstance(field, str) or not field or len(field.encode("utf-8")) > 256 for field in fields):
        raise ValueError("fields must be unique bounded nonempty strings")
    exact = {}
    normalized = {}
    seen_ids = set()
    total_bytes = 0
    for row in records:
        if not isinstance(row, dict) or len(row) > MAX_RECORD_FIELDS or any(not isinstance(key, str) for key in row):
            raise ValueError("each record must be a bounded JSON object")
        if "id" not in row or any(field not in row for field in fields):
            raise ValueError("each record must include id and every requested field")
        identifier = row["id"]
        if not isinstance(identifier, str) or not identifier or len(identifier.encode("utf-8")) > 256 or identifier in seen_ids:
            raise ValueError("record ids must be bounded unique strings")
        seen_ids.add(identifier)
        raw = {field: row[field] for field in fields}
        canonical = _canonical(raw)
        total_bytes += len(canonical.encode("utf-8"))
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("aggregate record byte limit exceeded")
        norm = {field: re.sub(r"\s+", " ", str(row[field]).strip().casefold()) for field in fields}
        for target, value in ((exact, canonical), (normalized, _canonical(norm))):
            key = hashlib.sha256(value.encode("utf-8")).hexdigest()
            target.setdefault(key, []).append(identifier)

    def groups(index):
        return sorted((sorted(values) for values in index.values() if len(values) > 1), key=lambda values: values)

    return {"exact": groups(exact), "normalized": groups(normalized)}


def run(data):
    if not isinstance(data, dict) or set(data) != {"records", "fields"}:
        raise ValueError("input must contain exactly records and fields")
    return find(**data)
