from __future__ import annotations
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any

PROJECT = "rag-citation-explorer"
REQUIRED_FIELDS = ["answer","claims","citations","uncovered_claims"]

def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())

def _string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_text(item) for item in value)

def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)

def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def build_citation_view(record: dict[str, Any]) -> dict[str, Any]:
    if not _text(record["answer"]) or not isinstance(record["claims"], list) or not record["claims"]:
        raise ValueError("answer and claims are required")
    claim_ids: list[str] = []
    for claim in record["claims"]:
        if not isinstance(claim, dict) or not _text(claim.get("id")) or not _text(claim.get("text")):
            raise ValueError("claims require id and text")
        claim_ids.append(claim["id"])
    if len(claim_ids) != len(set(claim_ids)) or not isinstance(record["citations"], list):
        raise ValueError("claim ids must be unique")
    links: dict[str, list[dict[str, str]]] = {claim_id: [] for claim_id in claim_ids}
    for citation in record["citations"]:
        if not isinstance(citation, dict) or citation.get("claim_id") not in links or not _text(citation.get("source")) or not _text(citation.get("chunk")):
            raise ValueError("citations must reference a claim, source, and chunk")
        links[citation["claim_id"]].append({"source": citation["source"], "chunk": citation["chunk"]})
    uncovered = [claim_id for claim_id in claim_ids if not links[claim_id]]
    if uncovered or record["uncovered_claims"] != []:
        raise ValueError("every claim must be covered")
    return {"coverage": 1.0, "claims": links}

def evaluate(record: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    artifact: Any = None
    if missing:
        status = "blocked"
        reason = "missing required fields: " + ", ".join(missing)
    else:
        try:
            artifact = build_citation_view(record)
            status = "passed"
            reason = "build_citation_view completed"
        except (TypeError, ValueError, KeyError) as exc:
            status = "failed"
            reason = str(exc)
    receipt = {"project": PROJECT, "status": status, "reason": reason, "record": record, "citation_view": artifact}
    receipt["evidence_sha256"] = sha256(_canonical(receipt).encode()).hexdigest()
    return receipt

