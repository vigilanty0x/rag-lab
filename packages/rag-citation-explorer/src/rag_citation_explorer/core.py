from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any

PROJECT = "rag-citation-explorer"
REQUIRED_FIELDS = ("answer", "claims", "citations", "sources")
MAX_INPUT_BYTES = 262_144
SHA256 = re.compile(r"[0-9a-f]{64}")
TOKEN = re.compile(r"[a-z0-9]+")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _text(value: Any, limit: int) -> bool:
    return isinstance(value, str) and 0 < len(value.strip()) <= limit and "\x00" not in value


def _tokens(value: str) -> set[str]:
    return set(TOKEN.findall(value.casefold()))


def build_citation_view(record: dict[str, Any]) -> dict[str, Any]:
    if not _text(record.get("answer"), 50_000):
        raise ValueError("answer must be a bounded string")
    claims = record.get("claims")
    sources = record.get("sources")
    citations = record.get("citations")
    if not isinstance(claims, list) or not 1 <= len(claims) <= 500 or not isinstance(sources, list) or not 1 <= len(sources) <= 200 or not isinstance(citations, list) or len(citations) > 2000:
        raise ValueError("claims, sources, or citations exceed bounds")
    claim_map: dict[str, str] = {}
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {"id", "text"} or not _text(claim["id"], 100) or not _text(claim["text"], 2000) or claim["id"] in claim_map:
            raise ValueError("claims require unique bounded id and text fields")
        claim_map[claim["id"]] = claim["text"]
    registry: dict[tuple[str, str], str] = {}
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"source_id", "chunks"} or not _text(source["source_id"], 200) or not isinstance(source["chunks"], list) or not 1 <= len(source["chunks"]) <= 1000:
            raise ValueError("sources require stable source_id and bounded chunks")
        for chunk in source["chunks"]:
            if not isinstance(chunk, dict) or set(chunk) != {"chunk_id", "text", "sha256"} or not _text(chunk["chunk_id"], 200) or not _text(chunk["text"], 20_000):
                raise ValueError("chunks require stable id, bounded text, and digest")
            key = (source["source_id"], chunk["chunk_id"])
            if key in registry or not isinstance(chunk["sha256"], str) or not SHA256.fullmatch(chunk["sha256"]) or sha256(chunk["text"].encode()).hexdigest() != chunk["sha256"]:
                raise ValueError("chunk ids must be unique and chunk digests must match trusted registry text")
            registry[key] = chunk["text"]
    links: dict[str, list[dict[str, Any]]] = {claim_id: [] for claim_id in claim_map}
    for citation in citations:
        required = {"claim_id", "source_id", "chunk_id", "quote", "start", "end"}
        if not isinstance(citation, dict) or set(citation) != required or citation["claim_id"] not in links or (citation["source_id"], citation["chunk_id"]) not in registry or not _text(citation["quote"], 5000):
            raise ValueError("citations must reference registered claims and chunks with an exact quote span")
        start, end = citation["start"], citation["end"]
        chunk = registry[(citation["source_id"], citation["chunk_id"])]
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool) or not 0 <= start < end <= len(chunk) or chunk[start:end] != citation["quote"]:
            raise ValueError("citation quote must exactly match its declared chunk span")
        claim_tokens = _tokens(claim_map[citation["claim_id"]])
        quote_tokens = _tokens(citation["quote"])
        supported = bool(claim_tokens) and claim_tokens <= quote_tokens
        links[citation["claim_id"]].append({**citation, "semantic_support": supported})
    structurally_covered = [claim_id for claim_id, items in links.items() if items]
    semantically_supported = [claim_id for claim_id, items in links.items() if any(item["semantic_support"] for item in items)]
    total = len(claim_map)
    return {
        "structural_coverage": len(structurally_covered) / total,
        "semantic_support_coverage": len(semantically_supported) / total,
        "supported_claims": semantically_supported,
        "unsupported_claims": [claim_id for claim_id in claim_map if claim_id not in semantically_supported],
        "claims": links,
        "rule": "exact registered quote span plus all normalized claim tokens contained in quote",
    }


def evaluate(record: Any) -> dict[str, Any]:
    artifact: Any = None
    safe_record = None
    try:
        if not isinstance(record, dict):
            raise ValueError("record must be a JSON object")
        if len(_canonical(record).encode()) > MAX_INPUT_BYTES:
            raise ValueError("record exceeds 262144 bytes")
        safe_record = record
        missing = [field for field in REQUIRED_FIELDS if field not in record]
        if missing:
            status, reason = "blocked", "missing required fields: " + ", ".join(missing)
        else:
            artifact = build_citation_view(record)
            if artifact["unsupported_claims"]:
                status, reason = "failed", "one or more claims lack conservative semantic support"
            else:
                status, reason = "passed", "all claims satisfy the conservative registered-quote support rule"
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        status, reason = "failed", str(exc)
    receipt = {"project": PROJECT, "status": status, "reason": reason, "record": safe_record, "citation_view": artifact}
    receipt["evidence_sha256"] = sha256(_canonical(receipt).encode()).hexdigest()
    return receipt
