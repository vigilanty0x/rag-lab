"""Bounded, deterministic lexical/vector rank fusion."""

from collections import Counter
import math
import re

MAX_DOCUMENTS = 10_000
MAX_QUERY_BYTES = 16_384
MAX_TEXT_BYTES = 1_000_000
MAX_TOTAL_TEXT_BYTES = 10_000_000
MAX_TOKENS = 1_000_000
MAX_VECTOR_DIMENSION = 4_096
MAX_LIMIT = 1_000
DOCUMENT_KEYS = {"id", "text", "vector", "query_vector"}


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _vector(value, name):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_VECTOR_DIMENSION:
        raise ValueError(f"{name} must be a bounded nonempty list")
    return [_number(component, name) for component in value]


def _cosine(left, right):
    left_norm = math.hypot(*left)
    right_norm = math.hypot(*right)
    if left_norm == 0 or right_norm == 0:
        return 0.0
    score = math.fsum((a / left_norm) * (b / right_norm) for a, b in zip(left, right))
    return max(-1.0, min(1.0, score))


def search(query, documents, *, alpha=0.5, limit=10):
    if not isinstance(query, str) or not query or len(query.encode("utf-8")) > MAX_QUERY_BYTES:
        raise ValueError("query must be a bounded nonempty string")
    if not isinstance(documents, list) or not 1 <= len(documents) <= MAX_DOCUMENTS:
        raise ValueError("documents must be a bounded nonempty list")
    alpha = _number(alpha, "alpha")
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be between zero and one")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError("limit must be a bounded positive integer")

    query_tokens = re.findall(r"\w+", query.casefold())
    if not query_tokens or len(query_tokens) > 1_024:
        raise ValueError("query token count is outside bounds")
    query_terms = set(query_tokens)
    results = []
    seen_ids = set()
    total_bytes = 0
    total_tokens = 0
    for document in documents:
        if not isinstance(document, dict) or set(document) != DOCUMENT_KEYS:
            raise ValueError("each document must contain exactly id, text, vector, and query_vector")
        identifier = document["id"]
        if not isinstance(identifier, str) or not identifier or len(identifier.encode("utf-8")) > 256:
            raise ValueError("document id must be a bounded nonempty string")
        if identifier in seen_ids:
            raise ValueError("document ids must be unique")
        seen_ids.add(identifier)
        text = document["text"]
        if not isinstance(text, str):
            raise ValueError("document text must be a string")
        text_bytes = len(text.encode("utf-8"))
        total_bytes += text_bytes
        if text_bytes > MAX_TEXT_BYTES or total_bytes > MAX_TOTAL_TEXT_BYTES:
            raise ValueError("document text byte limit exceeded")
        tokens = re.findall(r"\w+", text.casefold())
        total_tokens += len(tokens)
        if total_tokens > MAX_TOKENS:
            raise ValueError("document token limit exceeded")
        frequencies = Counter(tokens)
        lexical = sum(frequencies[term] for term in query_terms) / (len(tokens) or 1)
        query_vector = _vector(document["query_vector"], "query_vector")
        vector = _vector(document["vector"], "vector")
        if len(query_vector) != len(vector):
            raise ValueError("vector dimensions must match")
        semantic = _cosine(query_vector, vector)
        score = alpha * lexical + (1 - alpha) * semantic
        results.append({"id": identifier, "score": score, "lexical": lexical, "semantic": semantic})
    results.sort(key=lambda item: (-item["score"], item["id"]))
    return results[:limit]


def run(data):
    if not isinstance(data, dict) or not {"query", "documents"} <= set(data) or set(data) - {"query", "documents", "alpha", "limit"}:
        raise ValueError("input must contain query and documents only, with optional alpha and limit")
    return {"results": search(**data)}
