"""Content-bound corpus version comparison; no implicit ingestion or mutation.

The per-ID snapshot/diff capability follows dataset-versioner's existing
contract. This native adapter uses validated RAG documents and belongs to the
same workflow receipt; the historical package and its history stay intact.
"""
from __future__ import annotations

from .models import BenchmarkSuite, ContractError, canonical_sha256, content_sha256


def compare_corpora(previous: BenchmarkSuite, current: BenchmarkSuite) -> dict:
    if previous.suite_id != current.suite_id:
        raise ContractError("corpus versions must have the same suite_id")
    before = {document.source_id: document for document in previous.documents}
    after = {document.source_id: document for document in current.documents}
    changes = []
    unchanged = 0
    for source_id in sorted(before.keys() | after.keys()):
        old, new = before.get(source_id), after.get(source_id)
        left, right = old.to_dict() if old else None, new.to_dict() if new else None
        if left == right:
            unchanged += 1
            continue
        kind = "added" if old is None else "removed" if new is None else "modified"
        changes.append({
            "source_id": source_id, "kind": kind,
            "changed_fields": sorted(set(left or {}) | set(right or {})) if not old or not new
                              else sorted(key for key in left if left[key] != right[key]),
            "before_document_sha256": canonical_sha256(left) if left else None,
            "after_document_sha256": canonical_sha256(right) if right else None,
            "before_content_sha256": content_sha256(old.content) if old else None,
            "after_content_sha256": content_sha256(new.content) if new else None,
        })
    result = {
        "schema_version": "rag-lab/corpus-diff-v1", "suite_id": current.suite_id,
        "previous_suite_sha256": previous.digest, "current_suite_sha256": current.digest,
        "previous_version": previous.version, "current_version": current.version,
        "previous_evaluation_date": previous.evaluation_date.isoformat(),
        "current_evaluation_date": current.evaluation_date.isoformat(),
        "comparison_scope": "all_explicit_documents_including_rejected_documents",
        "chronology_verified": False, "source_mutation": False,
        "before_document_count": len(before), "after_document_count": len(after),
        "unchanged": unchanged,
        "counts": {kind: sum(row["kind"] == kind for row in changes) for kind in ("added", "removed", "modified")},
        "changes": changes,
    }
    return {**result, "diff_sha256": canonical_sha256(result)}
