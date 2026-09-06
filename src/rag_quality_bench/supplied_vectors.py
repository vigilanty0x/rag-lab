"""Explicit, bounded supplied vectors; provenance is declared, never authenticated.

Validation ports semantic-index-doctor's entry invariants, then binds every
entry to a single space and the canonical chunk/query bytes. Scoring ports the
retained hybrid-search-playground formula; no model or URL is called.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping

from .models import ContractError, canonical_sha256, content_sha256

MAX_VECTOR_BYTES = 32 * 1024 * 1024
MAX_VECTOR_SCALARS = 1_000_000
MAX_VECTOR_DIMENSION = 4096
MAX_VECTOR_CHUNKS = 10_000
MAX_VECTOR_QUERIES = 1001
VECTOR_SCHEMA = 'rag-lab/vectors-v1'
FIELDS = {'schema_version', 'suite_sha256', 'model', 'model_version', 'dimension', 'provenance', 'chunks', 'queries'}
ROW_FIELDS = {'id', 'text_sha256', 'model', 'model_version', 'vector'}


def _text(value: Any, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError('vector metadata must be nonempty text')
    try:
        if len(value.encode('utf-8')) > maximum:
            raise ContractError('vector metadata exceeds byte bound')
    except UnicodeError as exc:
        raise ContractError('vector metadata must be UTF-8') from exc
    return value


def _digest(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ContractError('vector digest must be lowercase SHA256')
    return value


def _vector(value: Any, dimension: int) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != dimension:
        raise ContractError('vector dimension mismatch')
    result = []
    for component in value:
        try:
            if isinstance(component, bool) or not isinstance(component, (float, int)) or not math.isfinite(component):
                raise ContractError('vector non_finite component')
            result.append(float(component))
        except (OverflowError, ValueError) as exc:
            raise ContractError('vector non_finite component') from exc
    norm = math.hypot(*result)
    if norm == 0:
        raise ContractError('vector zero_vector')
    if not math.isfinite(norm):
        raise ContractError('vector norm overflow')
    return tuple(result)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError('duplicate JSON key in vectors')
        result[key] = value
    return result


def load_vectors(path: str | Path) -> dict[str, Any]:
    """Read only this explicit local payload, never a referenced provenance URL."""
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_VECTOR_BYTES + 1)
    if len(raw) > MAX_VECTOR_BYTES:
        raise ContractError('vector payload exceeds byte bound')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ContractError('vector non_finite JSON')))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ContractError('invalid vector JSON') from exc
    if not isinstance(value, dict):
        raise ContractError('vector payload must be an object')
    return value


@dataclass(frozen=True)
class SuppliedVectors:
    """Immutable validated snapshot; public entry points revalidate supplied objects."""
    encoded: bytes
    digest: str
    chunks: Mapping[str, tuple[float, ...]]
    queries: Mapping[str, tuple[float, ...]]
    chunk_hashes: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.encoded)

    def query(self, text: str) -> tuple[float, ...]:
        try:
            return self.queries[content_sha256(text)]
        except KeyError as exc:
            raise ContractError('missing query vector for exact query text') from exc

    def metadata(self) -> dict[str, Any]:
        value = self.to_dict()
        return {'vectors_sha256': self.digest, 'model': value['model'],
                'model_version': value['model_version'], 'dimension': value['dimension'],
                'provenance': value['provenance'], 'origin_verified': False, 'provider_called': False}

    def bind_chunks(self, chunks) -> None:
        hashes = {c.chunk_id: content_sha256(c.text) for c in chunks}
        if len(hashes) != len(chunks) or hashes != dict(self.chunk_hashes):
            raise ContractError('vector chunk IDs/text hashes differ from exact valid corpus')


def validate_vectors(payload: Any, *, suite_sha256: str, chunks, queries=()) -> SuppliedVectors:
    """Validate the entire payload before any RetrievalIndex is constructed."""
    if isinstance(payload, SuppliedVectors):
        # Do not trust a caller-constructed dataclass or its derived maps.
        if not isinstance(payload.encoded, bytes) or len(payload.encoded) > MAX_VECTOR_BYTES:
            raise ContractError('vector payload exceeds byte bound')
        try:
            payload = json.loads(payload.encoded, object_pairs_hook=_unique)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise ContractError('invalid validated vector snapshot') from exc
    if not isinstance(payload, dict) or set(payload) != FIELDS:
        raise ContractError('vector payload fields differ from contract')
    if payload['schema_version'] != VECTOR_SCHEMA or _digest(payload['suite_sha256']) != suite_sha256:
        raise ContractError('vector schema or suite identity mismatch')
    model = _text(payload['model']); version = _text(payload['model_version'])
    dimension = payload['dimension']
    if type(dimension) is not int or not 1 <= dimension <= MAX_VECTOR_DIMENSION:
        raise ContractError('vector dimension must be a bounded positive integer')
    provenance = payload['provenance']
    if not isinstance(provenance, dict) or set(provenance) != {'kind', 'reference', 'artifact_sha256'} or provenance['kind'] != 'caller_declared':
        raise ContractError('vector provenance must be explicitly caller_declared')
    _text(provenance['reference'], 1024); _digest(provenance['artifact_sha256'])
    groups = [(payload['chunks'], MAX_VECTOR_CHUNKS), (payload['queries'], MAX_VECTOR_QUERIES)]
    for rows, maximum in groups:
        if not isinstance(rows, list) or not 1 <= len(rows) <= maximum:
            raise ContractError('vector entry count exceeds bound or is empty')
    if sum(len(rows) for rows, _ in groups) * dimension > MAX_VECTOR_SCALARS:
        raise ContractError('vector total scalar bound exceeded')
    maps = []; hashes = []
    for rows, _ in groups:
        vectors = {}; digests = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != ROW_FIELDS:
                raise ContractError('vector entry fields differ from contract')
            identifier = _text(row['id'])
            if identifier in vectors:
                raise ContractError('vector duplicate_id (chunk or query)')
            if row['model'] != model or row['model_version'] != version:
                raise ContractError('vector model/version mix')
            digests[identifier] = _digest(row['text_sha256'])
            vectors[identifier] = _vector(row['vector'], dimension)
        maps.append(MappingProxyType(vectors)); hashes.append(digests)
    if any(_digest(identifier) != digest for identifier, digest in hashes[1].items()):
        raise ContractError('query ID must be its exact UTF-8 text SHA256')
    # Copy only after bounded schema validation. JSON values retain their original
    # numeric representation for artifact identity; arithmetic uses immutable floats.
    try:
        encoded = (json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise ContractError('invalid vector payload') from exc
    if len(encoded) > MAX_VECTOR_BYTES:
        raise ContractError('vector payload exceeds byte bound')
    validated = SuppliedVectors(encoded, canonical_sha256(payload), maps[0], maps[1], MappingProxyType(hashes[0]))
    validated.bind_chunks(chunks)
    for query in queries:
        validated.query(query)
    return validated


def supplied_score(query: str, text: str, query_vector, vector, weight: float) -> tuple[float, float, float]:
    """Exact source formula, including signed scores and Unicode word tokens."""
    query_tokens = re.findall(r'\w+', query.casefold())
    if not query_tokens or len(query_tokens) > 1024 or len(query.encode('utf-8')) > 16384:
        raise ContractError('supplied query token/byte bound exceeded')
    tokens = re.findall(r'\w+', text.casefold())
    frequencies = Counter(tokens)
    lexical = sum(frequencies[term] for term in set(query_tokens)) / (len(tokens) or 1)
    left_norm = math.hypot(*query_vector); right_norm = math.hypot(*vector)
    # Divide before multiplication, as in the historical engine: finite large
    # components cannot overflow an intermediate product or squared norm.
    cosine = math.fsum((a / left_norm) * (b / right_norm) for a, b in zip(query_vector, vector))
    cosine = max(-1.0, min(1.0, cosine))
    return weight * lexical + (1.0 - weight) * cosine, lexical, cosine


def verify_vector_metadata(value: Any) -> bool:
    try:
        if not isinstance(value, dict) or set(value) != {'vectors_sha256', 'model', 'model_version', 'dimension', 'provenance', 'origin_verified', 'provider_called'}:
            return False
        _digest(value['vectors_sha256']); _text(value['model']); _text(value['model_version'])
        if type(value['dimension']) is not int or not 1 <= value['dimension'] <= MAX_VECTOR_DIMENSION:
            return False
        p = value['provenance']
        if not isinstance(p, dict) or set(p) != {'kind', 'reference', 'artifact_sha256'} or p['kind'] != 'caller_declared':
            return False
        _text(p['reference'], 1024); _digest(p['artifact_sha256'])
        return value['origin_verified'] is False and value['provider_called'] is False
    except (ContractError, TypeError, ValueError):
        return False
