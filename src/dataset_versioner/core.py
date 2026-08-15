"""Canonical, bounded JSON dataset snapshots and differences."""

import hashlib
import json
import math

MAX_ROWS = 100_000
MAX_FIELDS = 1_000
MAX_ROW_BYTES = 1_000_000
MAX_TOTAL_BYTES = 20_000_000


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("rows must contain finite JSON values") from exc


def snapshot(rows, id_field="id"):
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("rows must be a bounded list")
    if not isinstance(id_field, str) or not id_field or len(id_field.encode("utf-8")) > 256:
        raise ValueError("id_field must be a bounded nonempty string")
    indexed = {}
    total_bytes = 0
    for row in rows:
        if not isinstance(row, dict) or len(row) > MAX_FIELDS or any(not isinstance(key, str) for key in row):
            raise ValueError("each row must be a bounded JSON object")
        if id_field not in row:
            raise ValueError("row is missing id field")
        identifier = row[id_field]
        if isinstance(identifier, bool) or not isinstance(identifier, (str, int, float)):
            raise ValueError("row ids must be strings or finite numbers")
        if isinstance(identifier, float) and not math.isfinite(identifier):
            raise ValueError("row ids must be finite")
        key = str(identifier)
        if not key or len(key.encode("utf-8")) > 256 or key in indexed:
            raise ValueError("row ids must be bounded and unique after serialization")
        canonical = _canonical(row)
        size = len(canonical.encode("utf-8"))
        total_bytes += size
        if size > MAX_ROW_BYTES or total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("row byte limit exceeded")
        indexed[key] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    identity = sorted(indexed.items())
    version = hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest()
    return {"rows": indexed, "version": version}


def diff(before, after, id_field="id"):
    left = snapshot(before, id_field=id_field)
    right = snapshot(after, id_field=id_field)
    left_keys, right_keys = set(left["rows"]), set(right["rows"])
    return {
        "before": left["version"],
        "after": right["version"],
        "added": sorted(right_keys - left_keys),
        "removed": sorted(left_keys - right_keys),
        "changed": sorted(key for key in left_keys & right_keys if left["rows"][key] != right["rows"][key]),
    }


def run(data):
    if not isinstance(data, dict) or not {"before", "after"} <= set(data) or set(data) - {"before", "after", "id_field"}:
        raise ValueError("input must contain before and after with optional id_field")
    return diff(**data)
