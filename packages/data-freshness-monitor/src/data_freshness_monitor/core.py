"""Deterministic freshness decisions over aware timestamps."""

from datetime import datetime, timezone
import math

MAX_DATASETS = 100_000
MAX_AGE_SECONDS = 315_360_000


def _limit(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= MAX_AGE_SECONDS:
        raise ValueError(f"{name} must be a finite nonnegative bounded number")
    return float(value)


def _timestamp(value, name):
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError(f"{name} must be a bounded timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def monitor(datasets, *, now, default_max_age_seconds=3_600):
    if not isinstance(datasets, list) or not 1 <= len(datasets) <= MAX_DATASETS:
        raise ValueError("datasets must be a bounded nonempty list")
    current = _timestamp(now, "now")
    default_limit = _limit(default_max_age_seconds, "default_max_age_seconds")
    results = []
    seen = set()
    for dataset in datasets:
        if not isinstance(dataset, dict) or "id" not in dataset or set(dataset) - {"id", "observed_at", "max_age_seconds"}:
            raise ValueError("each dataset has an invalid shape")
        identifier = dataset["id"]
        if not isinstance(identifier, str) or not identifier or len(identifier.encode("utf-8")) > 256:
            raise ValueError("dataset id must be a bounded nonempty string")
        if identifier in seen:
            raise ValueError("dataset ids must be unique")
        seen.add(identifier)
        limit = _limit(dataset.get("max_age_seconds", default_limit), "max_age_seconds")
        if "observed_at" not in dataset or dataset["observed_at"] in (None, ""):
            results.append({"id": identifier, "status": "blocked", "age_seconds": None})
            continue
        observed = _timestamp(dataset["observed_at"], "observed_at")
        delta = (current - observed).total_seconds()
        if delta < 0:
            results.append({"id": identifier, "status": "future", "age_seconds": 0.0, "future_skew_seconds": -delta})
            continue
        age = float(delta)
        results.append({"id": identifier, "status": "fresh" if age <= limit else "stale", "age_seconds": age})
    return {"status": "healthy" if all(item["status"] == "fresh" for item in results) else "degraded", "datasets": results}


def run(data):
    if not isinstance(data, dict) or not {"datasets", "now"} <= set(data) or set(data) - {"datasets", "now", "default_max_age_seconds"}:
        raise ValueError("input must contain datasets and now with optional default_max_age_seconds")
    return monitor(**data)
