"""Reception tests: real retrieval, exact citations, bound quality evidence."""
import hashlib
import json

import pytest

from fixtures import suite, suite_dict
from rag_quality_bench.cli import main
from rag_quality_bench.engine import BenchmarkEngine
from rag_quality_bench.models import BenchmarkSuite, ContractError, content_sha256


def workflow_api():
    from rag_quality_bench.workflow import run_workflow, verify_workflow
    return run_workflow, verify_workflow


def test_versioned_workflow_reports_metadata_changes_and_replays(tmp_path):
    from dataclasses import replace
    previous = suite()
    current = replace(previous, version="1.2.4", documents=(replace(previous.documents[0], title="Revised title"),))
    run, verify = workflow_api()
    out = tmp_path / "versioned"
    receipt = run(current, previous_suite=previous, query="launch city", output=out)
    delta = json.loads((out / "corpus-diff.json").read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "rag-lab/workflow-v2"
    assert receipt["corpus_changes"] == {"added": 0, "removed": 0, "modified": 1}
    assert delta["changes"][0]["changed_fields"] == ["title"]
    assert delta["changes"][0]["before_content_sha256"] == delta["changes"][0]["after_content_sha256"]
    assert verify(out, current, previous_suite=previous) == receipt


def test_version_comparison_counts_added_removed_and_content_even_wrong_declared_hash():
    from dataclasses import replace
    from rag_quality_bench.versioning import compare_corpora
    previous = suite()
    original = previous.documents[0]
    previous = replace(previous, documents=(original, replace(original, source_id="removed")))
    current = replace(previous, documents=(replace(original, content=original.content + " Changed."), replace(original, source_id="added")))
    delta = compare_corpora(previous, current)
    assert delta["counts"] == {"added": 1, "removed": 1, "modified": 1}
    changed = next(row for row in delta["changes"] if row["source_id"] == "handbook")
    assert changed["before_content_sha256"] != changed["after_content_sha256"]
    assert changed["changed_fields"] == ["content"]
    assert "Changed." not in json.dumps(delta)
    assert "source_url" not in json.dumps(changed)


def test_versioned_workflow_requires_exact_previous_suite(tmp_path):
    from dataclasses import replace
    run, verify = workflow_api()
    model = suite()
    out = tmp_path / "versioned"
    run(model, previous_suite=model, query="launch", output=out)
    with pytest.raises(ContractError, match="previous suite"):
        verify(out, model)
    with pytest.raises(ContractError, match="comparison replay"):
        verify(out, model, previous_suite=replace(model, version="9.9.9"))


def test_rehashed_forged_corpus_delta_is_rejected(tmp_path):
    from rag_quality_bench.models import canonical_sha256
    run, verify = workflow_api()
    model = suite()
    out = tmp_path / "forged"
    run(model, previous_suite=model, query="launch", output=out)
    path = out / "corpus-diff.json"
    delta = json.loads(path.read_text(encoding="utf-8"))
    delta["unchanged"] = 900
    delta["diff_sha256"] = canonical_sha256({k:v for k,v in delta.items() if k != "diff_sha256"})
    path.write_text(json.dumps(delta), encoding="utf-8")
    with pytest.raises(ContractError, match="comparison replay"):
        verify(out, model, previous_suite=model)


def test_unrelated_corpus_baseline_is_rejected_before_output(tmp_path):
    from dataclasses import replace
    run, _ = workflow_api()
    out = tmp_path / "unrelated"
    with pytest.raises(ContractError, match="suite_id"):
        run(suite(), previous_suite=replace(suite(), suite_id="other"), query="launch", output=out)
    assert not out.exists()


def test_versioned_cli_roundtrip(tmp_path, capsys):
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(suite_dict()), encoding="utf-8")
    out = tmp_path / "cli-version"
    assert main(["workflow", "--suite", str(path), "--previous-suite", str(path), "--query", "launch city", "--output", str(out)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["corpus_changes"] == {"added": 0, "removed": 0, "modified": 0}
    assert main(["verify-workflow", "--suite", str(path), "--previous-suite", str(path), "--output", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True


def test_free_query_has_exact_citations_and_shared_index_identity():
    model = suite()
    engine = BenchmarkEngine(model)
    result = engine.search("launch city")
    assert result["status"] == "retrieved"
    assert result["index_sha256"] == engine.run()["index_sha256"]
    assert result["confidence"] is None
    assert result["quality"] == "not_measured"
    assert result["score_kind"] == "lexical_rank"
    assert result["hits"][0]["source_id"] == "handbook"
    for hit in result["hits"]:
        original = model.documents[0].content
        assert original[hit["char_start"]:hit["char_end"]] == hit["quote"]
        assert hashlib.sha256(hit["quote"].encode()).hexdigest() == hit["quote_sha256"]
        assert hit["document_sha256"] == model.documents[0].sha256


def test_citation_spans_preserve_unicode_crlf_and_overlap():
    raw = suite_dict()
    text = "  Café\r\nThe public handbook says the launch city is Geneva\tand the launch color is teal.  "
    raw["documents"][0].update(content=text, sha256=content_sha256(text))
    raw.update(chunk_size=8, chunk_overlap=3)
    result = BenchmarkEngine(BenchmarkSuite.from_dict(raw)).search("launch", limit=20)
    assert len(result["hits"]) >= 2
    for hit in result["hits"]:
        assert text[hit["char_start"]:hit["char_end"]] == hit["quote"]
        assert " ".join(hit["quote"].split()) == hit["text"]


@pytest.mark.parametrize("change,error", [
    ({"trust": "blocked"}, "trust_blocked"),
    ({"trust": "untrusted"}, "trust_untrusted"),
    ({"expires_at": "2026-01-01"}, "expired"),
    ({"observed_at": "2028-01-01"}, "observed_in_future"),
    ({"sha256": "0" * 64}, "hash_mismatch"),
])
def test_search_excludes_invalid_corpus(change, error):
    raw = suite_dict()
    raw["documents"][0].update(change)
    result = BenchmarkEngine(BenchmarkSuite.from_dict(raw)).search("launch city")
    assert result["status"] == "no_results"
    assert result["hits"] == []
    assert error in result["excluded"][0]["errors"]


@pytest.mark.parametrize("query,limit", [("", 3), ("x" * 10001, 3), (None, 3), ("launch", True), ("launch", 21), ("\ud800", 3)],
                         ids=["empty", "oversized", "not-text", "bool-limit", "large-limit", "invalid-utf8"])
def test_search_limits_are_enforced(query, limit):
    with pytest.raises(ContractError):
        BenchmarkEngine(suite()).search(query, limit=limit)


def test_hashed_hybrid_is_never_called_semantic_confidence():
    raw = suite_dict()
    raw["retrieval_strategy"] = "hybrid"
    result = BenchmarkEngine(BenchmarkSuite.from_dict(raw)).search("launch city")
    assert result["score_kind"] == "lexical_and_feature_hash_rank"
    assert result["embedding_model"] is None
    assert result["confidence"] is None


def test_workflow_connects_corpus_search_quality_and_receipt(tmp_path):
    run, verify = workflow_api()
    out = tmp_path / "run"
    receipt = run(suite(), query="launch city", output=out)
    assert receipt["status"] == "completed"
    assert receipt["quality_gate"]["passed"] is True
    assert receipt["query_quality"] == "not_measured"
    assert receipt["answer_generated"] is False
    assert receipt["evaluation_date"] == "2026-08-15"
    assert receipt["result_count"] > 0
    assert verify(out, suite()) == receipt
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    search = json.loads((out / "search.json").read_text(encoding="utf-8"))
    assert report["index_sha256"] == search["index_sha256"] == receipt["index_sha256"]
    assert (out / "report.md").read_text(encoding="utf-8").startswith("# RAG Quality Bench")


def test_bad_annotated_answer_keeps_evidence_but_fails_quality(tmp_path):
    run, verify = workflow_api()
    raw = suite_dict()
    raw["questions"][0]["response"]["claims"][0]["text"] = "Lunar colony sells orange bicycles"
    model = BenchmarkSuite.from_dict(raw)
    result = run(model, query="launch city", output=tmp_path / "red")
    assert result["status"] == "quality_failed"
    assert result["quality_gate"]["passed"] is False
    assert result["result_count"] > 0
    assert verify(tmp_path / "red", model) == result


def test_no_result_does_not_invent_an_answer(tmp_path):
    run, _ = workflow_api()
    receipt = run(suite(), query="xylophone quasar", output=tmp_path / "empty")
    assert receipt["status"] == "no_results"
    assert receipt["result_count"] == 0
    assert receipt["answer_generated"] is False
    assert receipt["quality_gate"]["passed"] is True


def test_existing_output_and_original_suite_are_preserved(tmp_path):
    run, _ = workflow_api()
    out = tmp_path / "existing"
    out.mkdir()
    marker = out / "sentinel.txt"
    marker.write_bytes(b"preserve")
    model = suite()
    before = model.to_dict()
    with pytest.raises((ContractError, FileExistsError)):
        run(model, query="launch", output=out)
    assert marker.read_bytes() == b"preserve"
    assert model.to_dict() == before
    assert list(out.iterdir()) == [marker]


def test_tampered_quote_even_rehashed_cannot_pass_replay(tmp_path):
    run, verify = workflow_api()
    from rag_quality_bench.models import canonical_sha256
    out = tmp_path / "tampered"
    run(suite(), query="launch city", output=out)
    path = out / "search.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["hits"][0]["quote"] = "fabricated quote"
    value["hits"][0]["quote_sha256"] = content_sha256("fabricated quote")
    path.write_text(json.dumps(value), encoding="utf-8")
    receipt_path = out / "workflow.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["artifacts"]["search.json"] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    receipt.pop("receipt_sha256")
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ContractError):
        verify(out, suite())


def test_wrong_corpus_or_missing_completion_receipt_is_refused(tmp_path):
    run, verify = workflow_api()
    out = tmp_path / "run"
    run(suite(), query="launch", output=out)
    raw = suite_dict()
    raw["documents"][0]["title"] += " changed"
    with pytest.raises(ContractError):
        verify(out, BenchmarkSuite.from_dict(raw))
    partial = tmp_path / "partial"
    partial.mkdir()
    with pytest.raises((ContractError, FileNotFoundError)):
        verify(partial, suite())


def test_cli_workflow_and_replay_use_real_engine(tmp_path, capsys):
    source = tmp_path / "suite.json"
    source.write_text(json.dumps(suite_dict()), encoding="utf-8")
    out = tmp_path / "cli"
    assert main(["workflow", "--suite", str(source), "--query", "launch city", "--output", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"
    assert main(["verify-workflow", "--suite", str(source), "--output", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True


def test_partial_write_has_no_completion_receipt_and_preserves_evidence(tmp_path, monkeypatch):
    run, verify = workflow_api()
    import rag_quality_bench.workflow as module
    original = module._write
    def interrupted(directory, name, payload):
        if name == "search.json":
            raise OSError("synthetic interruption")
        return original(directory, name, payload)
    monkeypatch.setattr(module, "_write", interrupted)
    out = tmp_path / "interrupted"
    with pytest.raises(OSError):
        run(suite(), query="launch city", output=out)
    assert (out / "index.json").is_file()
    assert (out / "report.json").is_file()
    assert not (out / "workflow.json").exists()
    with pytest.raises(ContractError):
        verify(out, suite())


@pytest.mark.parametrize("threshold", [True, -0.1, 1.1, float("nan"), float("inf")])
def test_invalid_quality_threshold_never_creates_output(tmp_path, threshold):
    run, _ = workflow_api()
    out = tmp_path / "invalid"
    with pytest.raises(ContractError):
        run(suite(), query="launch", output=out, minimum_pass_rate=threshold)
    assert not out.exists()


def test_canonical_namespace_exposes_same_integrated_api():
    import rag_lab
    run, verify = workflow_api()
    assert rag_lab.run_workflow is run
    assert rag_lab.verify_workflow is verify
