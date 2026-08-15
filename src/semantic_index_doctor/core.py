"""Fail-closed validation for bounded semantic-index entries."""

import math

MAX_ENTRIES = 100_000
MAX_DIMENSION = 4_096


def diagnose(entries, *, expected_dimension):
    if isinstance(expected_dimension, bool) or not isinstance(expected_dimension, int) or not 1 <= expected_dimension <= MAX_DIMENSION:
        raise ValueError("expected_dimension must be a bounded positive integer")
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise ValueError("entries must be a bounded nonempty list")
    issues = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"id", "vector"}:
            raise ValueError("each entry must contain exactly id and vector")
        identifier = entry["id"]
        if not isinstance(identifier, str) or not identifier or len(identifier.encode("utf-8")) > 256:
            raise ValueError("entry id must be a bounded nonempty string")
        if identifier in seen:
            issues.append({"id": identifier, "issue": "duplicate_id"})
        seen.add(identifier)
        vector = entry["vector"]
        if not isinstance(vector, list) or len(vector) != expected_dimension:
            issues.append({"id": identifier, "issue": "dimension"})
            continue
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector):
            issues.append({"id": identifier, "issue": "non_finite"})
            continue
        if math.hypot(*vector) == 0:
            issues.append({"id": identifier, "issue": "zero_vector"})
    return {"status": "healthy" if not issues else "blocked", "entries": len(entries), "issues": issues}


def run(data):
    if not isinstance(data, dict) or set(data) != {"entries", "expected_dimension"}:
        raise ValueError("input must contain exactly entries and expected_dimension")
    return diagnose(**data)
