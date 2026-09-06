# One RAG Lab workflow

RAG Lab searches an explicitly supplied corpus and produces a replayable evidence directory in one operation. It reuses the existing `BenchmarkSuite`, `BenchmarkEngine`, `RetrievalIndex`, report validator, and Markdown renderer. It does not invoke the copied package CLIs or create a second retrieval engine.

```bash
rag-lab workflow --suite examples/suite.json --query "launch date" --output evidence-run-01
rag-lab verify-workflow --suite examples/suite.json --output evidence-run-01
```

The output parent must exist; `evidence-run-01` must not. The synthetic example contains deliberate failures, so its default quality gate returns exit 1 with all evidence preserved. A positive fixture must actually pass the required annotated questions; lowering the threshold changes the declared policy, not the observed results.

For an explicit prior version of the same suite, add `--previous-suite old-suite.json`
to both commands. The same workflow then writes `corpus-diff.json` and a v2 receipt:
added, removed, modified and unchanged document counts, exact changed field names,
actual content hashes and full document fingerprints. Changes to provenance, trust,
dates or titles count even when content is unchanged. Rejected documents remain
part of this comparison; the ordinary quality gate still decides admissibility.
The diff contains IDs/hashes/field names, no content or provenance URLs. Replay
requires both exact suites and recomputes the diff, so a self-rehashed alteration
fails. These are caller-selected versions, not proof of chronological order.
Without this option the existing v1 workflow remains unchanged. The native adapter
implements the per-ID snapshot/diff capability identified in `dataset-versioner`;
its historical package remains intact. No source or historical corpus is modified.

## Inputs and Python API

The existing suite JSON is the complete input contract: up to 200 documents and 500 annotated questions in 5 MB, explicit document content, SHA-256, provenance label, license, trust and observation/expiry dates, a fixed evaluation date, chunking settings, and one retrieval strategy. No directory is scanned and no source URL is fetched. Use public/synthetic or explicitly approved local content. `search.json` contains source quotes and the query, so choose its destination accordingly.

```python
from pathlib import Path
from rag_lab import BenchmarkSuite, run_workflow, verify_workflow

# Enforce the 5 MB limit before reading untrusted files; the CLI does this.
suite = BenchmarkSuite.from_json(Path("suite.json").read_text(encoding="utf-8"))
receipt = run_workflow(suite, query="launch city", output="evidence-run-02",
                       minimum_pass_rate=1.0, limit=3)
checked = verify_workflow("evidence-run-02", suite)
```

`BenchmarkEngine(suite).search(query, limit=3)` is the same in-memory retrieval API without writing a workflow. A query is 1–10,000 characters; the result limit is 1–20. The CLI accepts `--minimum-pass-rate` in 0–1 and `--limit`. The suite owns the retrieval strategy and evaluation date.

## Connected stages

1. Validate document hash, trust, freshness and future dates against the supplied evaluation date. Excluded documents remain listed with reasons. The evaluation date is not a claim of current freshness.
2. Build the existing content-bound index and execute the free query through its ranking implementation.
3. Bind every returned chunk to the full document SHA, exact quote SHA and `[char_start, char_end)` offsets in Unicode code points. `quote` preserves source whitespace and Unicode; `text` is the existing whitespace-normalized indexed chunk. Titles, license and provenance labels remain caller-supplied, never fetched.
4. Run all annotated benchmark questions and their supplied responses through the existing retrieval/citation/claim checks. Verify the resulting report and require the search and report to use the same index digest.
5. Write and read back `index.json`, `report.json`, `search.json`, and `report.md` in the new directory. Write `workflow.json` last, binding file bytes, suite/index/report digests, query, counts, policy and observed outcome. Never overwrite an existing run. Interrupted writes preserve partial evidence without a completion receipt.

The workflow returns `completed` only when the benchmark gate passes and the query has hits. It returns `quality_failed` when the benchmark gate fails, even if the query has hits; `no_results` when the benchmark passes but no query evidence is retrieved. CLI exits: 0 completed, 1 quality failure/no results, 2 invalid input or write failure. `verify-workflow` exits 0 for any internally valid preserved outcome, including a correctly recorded quality failure; this verifies evidence, not release approval.

## Quality and integrity limits

`query_quality=not_measured`, `confidence=null` and `answer_generated=false` are deliberate. The benchmark's pass rate applies to its annotated questions and supplied responses, not the new query. Existing claim checks measure token coverage and do not prove semantic entailment. Rank values are not confidence probabilities. BM25, TF-IDF and overlap are lexical; hybrid adds deterministic feature hashing, not learned semantic embeddings. The tokenizer remains the existing ASCII-oriented baseline.

Replay verifies all file hashes, reruns retrieval and exact citation construction against the supplied corpus, recomputes the benchmark semantic digest, and validates the human-readable report. A changed quote cannot pass merely by updating its hashes. Hashes prove consistency with supplied bytes; they do not authenticate a publisher. Latency is observed during evaluation and excluded from deterministic semantic comparison, as in existing report schema 2.0.

There are no model calls, downloads, implicit ingestion, remote publication, or changes to source files. Existing namespaces, commands and report schemas 1.0/2.0 remain compatible. Separate historical packages remain visible migration sources; this workflow does not claim that all their distinct functions have been consolidated.
