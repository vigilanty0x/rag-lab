"""One offline corpus -> retrieval -> quality -> replayable evidence workflow."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

from .engine import BenchmarkEngine
from .models import BenchmarkSuite, ContractError, canonical_sha256
from .reporting import MAX_REPORT_BYTES, render_markdown, verify_report
from .retrieval import MAX_MANIFEST_BYTES
from .versioning import compare_corpora
from .supplied_vectors import MAX_VECTOR_BYTES, SuppliedVectors
from .file_intake import MAX_INTAKE_BYTES, prepare_file_suite, validate_intake, verify_observation
from .models import MAX_SUITE_BYTES


ARTIFACT_LIMITS = {
    "index.json": MAX_MANIFEST_BYTES,
    "report.json": MAX_REPORT_BYTES,
    "search.json": 8 * 1024 * 1024,
    "report.md": MAX_REPORT_BYTES,
}
RECEIPT_LIMIT = 64 * 1024
CORPUS_DIFF_LIMIT = 8 * 1024 * 1024
INTAKE_LIMITS = {"intake.json": MAX_INTAKE_BYTES, "file-observation.json": MAX_INTAKE_BYTES, "suite.json": MAX_SUITE_BYTES}


def _threshold(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not 0 <= value <= 1 or not math.isfinite(value):
        raise ContractError("minimum pass rate must be a finite number between 0 and 1")
    return float(value)


def _encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _decode(raw: bytes) -> dict[str, Any]:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContractError("duplicate key in workflow artifact")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ContractError("nonfinite JSON")))
    except (ValueError, UnicodeError) as exc:
        raise ContractError("invalid workflow JSON") from exc
    if not isinstance(value, dict):
        raise ContractError("workflow artifact must be an object")
    return value


def _directory(path: str | Path) -> Path:
    target = Path(path).absolute()
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (target, *target.parents)):
        raise ContractError("workflow directory cannot traverse a link or junction")
    return target


def _read(directory: Path, name: str, limit: int) -> bytes:
    path = directory / name  # names originate only from fixed internal constants
    if path.is_symlink() or not path.is_file():
        raise ContractError("workflow artifact is missing or is a link")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ContractError("workflow artifact exceeds its size limit")
    return raw


def _write(directory: Path, name: str, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(directory / name, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _artifact_metadata(payloads: dict[str, bytes]) -> dict[str, dict[str, Any]]:
    return {name: {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
            for name, payload in payloads.items()}


def _receipt(suite: BenchmarkSuite, report: dict, search: dict, artifacts: dict, minimum: float,
             corpus_diff: dict | None = None, intake_evidence: dict | None = None) -> dict:
    gate = report["metrics"]["pass_rate"] >= minimum
    status = "quality_failed" if not gate else ("completed" if search["hits"] else "no_results")
    unsigned = {
        "schema_version": "rag-lab/workflow-v1", "status": status,
        "suite_sha256": suite.digest, "evaluation_date": suite.evaluation_date.isoformat(),
        "index_sha256": report["index_sha256"], "report_semantic_sha256": report["semantic_sha256"],
        "query_sha256": hashlib.sha256(search["query"].encode("utf-8")).hexdigest(),
        "query_quality": "not_measured", "answer_generated": False, "network_used": False,
        "document_count": search["document_count"], "valid_document_count": search["valid_document_count"],
        "result_count": len(search["hits"]), "score_kind": search["score_kind"],
        "quality_gate": {"scope": "provided_annotated_questions_and_responses",
                         "minimum_pass_rate": minimum, "pass_rate": report["metrics"]["pass_rate"], "passed": gate},
        "artifacts": artifacts,
    }
    if corpus_diff is not None:
        unsigned.update(schema_version="rag-lab/workflow-v2",
                        previous_suite_sha256=corpus_diff["previous_suite_sha256"],
                        corpus_diff_sha256=corpus_diff["diff_sha256"],
                        corpus_changes=corpus_diff["counts"])
    if search["strategy"] == "supplied":
        unsigned.update(schema_version="rag-lab/workflow-v3", vectors_sha256=search["embedding_model"]["vectors_sha256"],
                        embedding_origin_verified=False, provider_called=False)
    if intake_evidence is not None:
        unsigned.update(schema_version="rag-lab/workflow-v4", template_suite_sha256=intake_evidence["template_suite_sha256"],
                        intake_sha256=intake_evidence["intake_sha256"], file_observation_sha256=canonical_sha256(intake_evidence),
                        file_replacement_policy="replace_all_inline_documents")
    return {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}


def run_workflow(suite: BenchmarkSuite, *, query: str, output: str | Path,
                 minimum_pass_rate: float = 1.0, limit: int | None = None,
                 previous_suite: BenchmarkSuite | None = None,
                 vectors: dict[str, Any] | SuppliedVectors | None = None, root=None,
                 intake: dict[str, Any] | None = None) -> dict[str, Any]:
    """Use only the caller-supplied corpus; preserve failures and original files.

    The output directory must be new and its parent must exist. Completion is
    recorded last. A failed/interrupted write leaves its partial evidence intact
    and cannot be mistaken for a completed run by verify_workflow.

    For suite.retrieval_strategy == "supplied", vectors must contain the exact
    chunk vectors and every annotated/free-query vector. They are validated
    before index construction and copied into vectors.json. An explicit intake
    replaces every inline document and binds the rebuilt suite plus measured
    file observations in a v4 receipt; supplied vectors must bind that suite.
    """
    minimum = _threshold(minimum_pass_rate)
    target = _directory(output)
    if target.exists():
        raise ContractError("workflow output already exists; choose a new directory")
    if not target.parent.is_dir():
        raise ContractError("workflow output parent must already exist")
    intake_evidence = None
    if intake is not None:
        intake = validate_intake(intake)
        suite, intake_evidence = prepare_file_suite(suite, root=root, intake=intake)
    elif root is not None:
        raise ContractError("input root requires an explicit intake manifest")
    corpus_diff = compare_corpora(previous_suite, suite) if previous_suite is not None else None
    engine = BenchmarkEngine(suite, vectors=vectors)
    search = engine.search(query, limit=limit)
    report = engine.run()
    if not verify_report(report) or search["index_sha256"] != report["index_sha256"]:
        raise ContractError("search and quality report are not bound to the same valid index")
    payloads = {
        "index.json": _encode(report["index_manifest"]),
        "report.json": _encode(report), "search.json": _encode(search),
        "report.md": render_markdown(report).encode("utf-8"),
    }
    limits = dict(ARTIFACT_LIMITS)
    if intake_evidence is not None:
        payloads.update({"intake.json": _encode(intake), "file-observation.json": _encode(intake_evidence),
                         "suite.json": _encode(suite.to_dict())})
        limits.update(INTAKE_LIMITS)
    if engine.vectors is not None:
        payloads["vectors.json"] = engine.vectors.encoded
        limits["vectors.json"] = MAX_VECTOR_BYTES
    if corpus_diff is not None:
        payloads["corpus-diff.json"] = _encode(corpus_diff)
        limits["corpus-diff.json"] = CORPUS_DIFF_LIMIT
    for name, payload in payloads.items():
        if len(payload) > limits[name]:
            raise ContractError("workflow artifact exceeds its size limit")
    receipt = _receipt(suite, report, search, _artifact_metadata(payloads), minimum, corpus_diff, intake_evidence)
    target.mkdir(mode=0o700, exist_ok=False)
    for name, payload in payloads.items():
        _write(target, name, payload)
        if _read(target, name, limits[name]) != payload:
            raise ContractError("workflow artifact read-back differs from written bytes")
    _write(target, "workflow.json", _encode(receipt))
    return receipt


def verify_workflow(output: str | Path, suite: BenchmarkSuite, *,
                    previous_suite: BenchmarkSuite | None = None,
                    vectors: dict[str, Any] | SuppliedVectors | None = None, root=None,
                    intake: dict[str, Any] | None = None) -> dict[str, Any]:
    """Recompute evidence from the supplied corpus; a self-hash alone is insufficient.

    This proves consistency with these supplied bytes, not authenticity of their
    publisher or semantic truth of an answer. No source URL is dereferenced.
    A v3 replay requires the same explicit vectors input; the artifact itself
    never replaces that caller-supplied reference.
    A v4 replay also requires the same explicit file manifest and readable root.
    Historical read timestamps are retained, not authenticated by replay.
    """
    target = _directory(output)
    receipt = _decode(_read(target, "workflow.json", RECEIPT_LIMIT))
    file_based = receipt.get("schema_version") == "rag-lab/workflow-v4"
    if file_based != (intake is not None) or (not file_based and root is not None):
        raise ContractError("file workflow requires the same explicit intake manifest and root")
    supplied = receipt.get("schema_version") == "rag-lab/workflow-v3" or (file_based and suite.retrieval_strategy == "supplied")
    if supplied != (suite.retrieval_strategy == "supplied"):
        raise ContractError("supplied workflow requires the same explicit strategy and vectors")
    versioned = receipt.get("schema_version") == "rag-lab/workflow-v2" or ((supplied or file_based) and "previous_suite_sha256" in receipt)
    if versioned != (previous_suite is not None):
        raise ContractError("versioned workflow requires the same explicit previous suite")
    payloads = {name: _read(target, name, maximum) for name, maximum in ARTIFACT_LIMITS.items()}
    intake_evidence = None
    if file_based:
        intake = validate_intake(intake)
        for name, maximum in INTAKE_LIMITS.items():
            payloads[name] = _read(target, name, maximum)
        if payloads["intake.json"] != _encode(intake):
            raise ContractError("intake manifest replay mismatch")
        suite, measured = prepare_file_suite(suite, root=root, intake=intake)
        intake_evidence = _decode(payloads["file-observation.json"])
        verify_observation(intake_evidence, measured)
        if payloads["suite.json"] != _encode(suite.to_dict()):
            raise ContractError("file suite replay mismatch")
    corpus_diff = None
    if versioned:
        payloads["corpus-diff.json"] = _read(target, "corpus-diff.json", CORPUS_DIFF_LIMIT)
        corpus_diff = compare_corpora(previous_suite, suite)
        if _decode(payloads["corpus-diff.json"]) != corpus_diff:
            raise ContractError("corpus version comparison replay mismatch")
    try:
        report = _decode(payloads["report.json"])
        search = _decode(payloads["search.json"])
        manifest = _decode(payloads["index.json"])
        minimum = _threshold(receipt["quality_gate"]["minimum_pass_rate"])
        engine = BenchmarkEngine(suite, vectors=vectors)
        if engine.vectors is not None:
            payloads["vectors.json"] = _read(target, "vectors.json", MAX_VECTOR_BYTES)
            if payloads["vectors.json"] != engine.vectors.encoded:
                raise ContractError("supplied vectors replay mismatch")
        if not verify_report(report) or not engine.verify_index_manifest(manifest):
            raise ContractError("invalid quality report or index manifest")
        if report["index_manifest"] != manifest or report["suite_sha256"] != suite.digest:
            raise ContractError("workflow source/index identity mismatch")
        if search != engine.search(search["query"], limit=search["limit"]):
            raise ContractError("search/citation replay mismatch")
        if report["semantic_sha256"] != engine.run()["semantic_sha256"]:
            raise ContractError("quality evaluation replay mismatch")
        if payloads["report.md"] != render_markdown(report).encode("utf-8"):
            raise ContractError("rendered report does not match verified quality evidence")
        expected = _receipt(suite, report, search, _artifact_metadata(payloads), minimum, corpus_diff, intake_evidence)
        if receipt != expected:
            raise ContractError("workflow receipt does not match its verified artifacts")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ContractError("workflow contract is incomplete or invalid") from exc
    return receipt
