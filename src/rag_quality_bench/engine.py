"""Traceable chunk, index, retrieval, claim, and evidence evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import time
from typing import Any, Callable

from .models import BenchmarkSuite, Claim, Document, canonical_sha256


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(token.lower() for token in TOKEN_RE.findall(text) if len(token) > 1)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_id: str
    ordinal: int
    text: str
    document_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "ordinal": self.ordinal,
            "text": self.text,
            "document_sha256": self.document_sha256,
        }


def chunk_document(document: Document, size: int, overlap: int) -> tuple[Chunk, ...]:
    words = document.content.split()
    chunks: list[Chunk] = []
    start = 0
    ordinal = 0
    step = size - overlap
    while start < len(words):
        end = min(len(words), start + size)
        text = " ".join(words[start:end])
        chunk_id = f"{document.source_id}:{ordinal}:{start}-{end}"
        chunks.append(Chunk(chunk_id, document.source_id, ordinal, text, document.sha256))
        ordinal += 1
        if end == len(words):
            break
        start += step
    return tuple(chunks)


def retrieval_score(query: str, chunk: Chunk) -> float:
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return 0.0
    chunk_tokens = set(tokenize(chunk.text))
    return len(query_tokens & chunk_tokens) / len(query_tokens)


def claim_support(claim: Claim, documents: dict[str, Document]) -> tuple[bool, float, list[str]]:
    claim_tokens = set(tokenize(claim.text))
    if not claim_tokens:
        return False, 0.0, ["empty_claim"]
    missing = [source_id for source_id in claim.citations if source_id not in documents]
    if missing:
        return False, 0.0, [f"missing_source:{source_id}" for source_id in missing]
    evidence_tokens: set[str] = set()
    for source_id in claim.citations:
        evidence_tokens.update(tokenize(documents[source_id].content))
    coverage = len(claim_tokens & evidence_tokens) / len(claim_tokens)
    reasons: list[str] = [] if coverage >= 0.75 else ["claim_not_supported"]
    return coverage >= 0.75, coverage, reasons


class BenchmarkEngine:
    def __init__(self, suite: BenchmarkSuite, *, clock: Callable[[], int] | None = None):
        self.suite = suite
        self.clock = clock or time.perf_counter_ns

    def inventory(self) -> dict[str, Any]:
        document_rows: list[dict[str, Any]] = []
        valid_documents: dict[str, Document] = {}
        hashes: dict[str, list[str]] = {}
        for document in self.suite.documents:
            errors = document.validation_errors(self.suite.evaluation_date)
            document_rows.append({
                "source_id": document.source_id,
                "sha256": document.sha256,
                "valid": not errors,
                "errors": errors,
            })
            hashes.setdefault(document.sha256, []).append(document.source_id)
            if not errors:
                valid_documents[document.source_id] = document
        duplicates = [sorted(ids) for ids in hashes.values() if len(ids) > 1]
        return {
            "suite_sha256": self.suite.digest,
            "document_count": len(self.suite.documents),
            "valid_document_count": len(valid_documents),
            "fresh_coverage": len(valid_documents) / len(self.suite.documents),
            "duplicates": sorted(duplicates),
            "documents": document_rows,
        }

    def _index(self, valid_documents: dict[str, Document]) -> tuple[Chunk, ...]:
        chunks = [
            chunk
            for source_id in sorted(valid_documents)
            for chunk in chunk_document(
                valid_documents[source_id], self.suite.chunk_size, self.suite.chunk_overlap
            )
        ]
        return tuple(chunks)

    def run(self) -> dict[str, Any]:
        inventory = self.inventory()
        valid_documents = {
            document.source_id: document
            for document in self.suite.documents
            if not document.validation_errors(self.suite.evaluation_date)
        }
        chunks = self._index(valid_documents)
        records: list[dict[str, Any]] = []
        for question in self.suite.questions:
            started = self.clock()
            ranked = sorted(
                (
                    (retrieval_score(question.text, chunk), chunk)
                    for chunk in chunks
                ),
                key=lambda item: (-item[0], item[1].chunk_id),
            )
            retrieved = [
                {"score": round(score, 6), **chunk.to_dict()}
                for score, chunk in ranked[: self.suite.retrieval_k]
                if score > 0
            ]
            elapsed_ms = max(0.0, (self.clock() - started) / 1_000_000)
            retrieved_sources = {item["source_id"] for item in retrieved}
            expected = set(question.expected_source_ids)
            recall = 1.0 if not expected else len(expected & retrieved_sources) / len(expected)
            claim_rows: list[dict[str, Any]] = []
            for claim in question.response.claims:
                supported, coverage, reasons = claim_support(claim, valid_documents)
                claim_rows.append({
                    "text": claim.text,
                    "citations": list(claim.citations),
                    "supported": supported,
                    "token_coverage": round(coverage, 6),
                    "reasons": reasons,
                })
            citations = {
                citation
                for claim in question.response.claims
                for citation in claim.citations
            }
            citation_errors = sorted(citations - retrieved_sources)
            citations_valid = not citation_errors and citations.issubset(valid_documents)
            abstained = question.response.answer is None
            no_answer_correct = abstained if question.no_answer else not abstained
            grounded = all(row["supported"] for row in claim_rows) if claim_rows else question.no_answer and abstained
            passed = recall == 1.0 and citations_valid and no_answer_correct and grounded
            failures: list[str] = []
            if recall < 1.0:
                failures.append("retrieval_miss")
            if not citations_valid:
                failures.append("invalid_citation")
            if not no_answer_correct:
                failures.append("no_answer_mismatch")
            if not grounded:
                failures.append("ungrounded_claim")
            records.append({
                "question_id": question.question_id,
                "adversarial": question.adversarial,
                "expected_source_ids": list(question.expected_source_ids),
                "retrieved": retrieved,
                "retrieval_latency_ms": round(elapsed_ms, 6),
                "recall_at_k": recall,
                "no_answer_correct": no_answer_correct,
                "citations_valid": citations_valid,
                "citation_errors": citation_errors,
                "claims": claim_rows,
                "grounded": grounded,
                "passed": passed,
                "failures": failures,
            })
        claim_rows = [claim for record in records for claim in record["claims"]]
        answerable = [record for record, question in zip(records, self.suite.questions) if not question.no_answer]
        no_answer = [record for record, question in zip(records, self.suite.questions) if question.no_answer]
        metrics = {
            "recall_at_k": sum(record["recall_at_k"] for record in answerable) / len(answerable) if answerable else 1.0,
            "groundedness": sum(1 for claim in claim_rows if claim["supported"]) / len(claim_rows) if claim_rows else 1.0,
            "no_answer_accuracy": sum(1 for record in no_answer if record["no_answer_correct"]) / len(no_answer) if no_answer else 1.0,
            "fresh_coverage": inventory["fresh_coverage"],
            "pass_rate": sum(1 for record in records if record["passed"]) / len(records),
            "mean_retrieval_latency_ms": sum(record["retrieval_latency_ms"] for record in records) / len(records),
            "retrieval_k": self.suite.retrieval_k,
        }
        semantic = {
            "suite_sha256": self.suite.digest,
            "index_sha256": canonical_sha256([chunk.to_dict() for chunk in chunks]),
            "inventory": inventory,
            "metrics": {key: value for key, value in metrics.items() if "latency" not in key},
            "records": [
                {key: value for key, value in record.items() if key != "retrieval_latency_ms"}
                for record in records
            ],
        }
        return {
            "schema_version": "1.0",
            "suite_id": self.suite.suite_id,
            "suite_version": self.suite.version,
            **semantic,
            "metrics": metrics,
            "records": records,
            "semantic_sha256": canonical_sha256(semantic),
        }


def evaluate_suite(suite: BenchmarkSuite) -> dict[str, Any]:
    return BenchmarkEngine(suite).run()


def compare_reports(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    metric_keys = ["recall_at_k", "groundedness", "no_answer_accuracy", "fresh_coverage", "pass_rate"]
    deltas = {
        key: candidate.get("metrics", {}).get(key, 0) - baseline.get("metrics", {}).get(key, 0)
        for key in metric_keys
    }
    baseline_records = {record["question_id"]: record for record in baseline.get("records", [])}
    candidate_records = {record["question_id"]: record for record in candidate.get("records", [])}
    changed: list[dict[str, Any]] = []
    for question_id in sorted(set(baseline_records) | set(candidate_records)):
        before = baseline_records.get(question_id)
        after = candidate_records.get(question_id)
        if before is None or after is None or before.get("passed") != after.get("passed") or before.get("retrieved") != after.get("retrieved"):
            changed.append({
                "question_id": question_id,
                "baseline_passed": None if before is None else before.get("passed"),
                "candidate_passed": None if after is None else after.get("passed"),
            })
    return {
        "baseline_semantic_sha256": baseline.get("semantic_sha256"),
        "candidate_semantic_sha256": candidate.get("semantic_sha256"),
        "metric_deltas": deltas,
        "changed_questions": changed,
    }

