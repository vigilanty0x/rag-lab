# RAG Lab

Use an explicit local file list through `workflow --intake --input-root` to
replace the suite's inline documents with measured UTF-8 bytes. Paths, declared
hashes, dates and replay are checked; no directories are scanned or sources
deleted. See [File intake](docs/FILE-INTAKE.md) for the runnable example and limits.

Explicit offline vectors are available through `workflow --vectors` when the
suite selects `supplied`. The payload binds model/version, dimensions and exact
chunk/query hashes; no model is called. See [Supplied vectors](docs/SUPPLIED-VECTORS.md)
for the runnable example, signed ranking, refusal conditions and replay contract.

The integrated workflow also accepts `--previous-suite` to bind exact corpus
version changes to the same retrieval, quality and citation receipt. See
[Integrated workflow](docs/INTEGRATED-WORKFLOW.md).

RAG Lab is a dependency-free, offline evaluation laboratory for retrieval-augmented generation systems. It compares reproducible retrieval strategies, scores answer and ranking quality, records content-bound index manifests, sweeps bounded configurations, and produces verifiable JSON plus human-readable Markdown or HTML evidence.

The proven `rag-quality-bench` engine remains the compatibility distribution and CLI. New integrations should use **RAG Lab** as the product identity, `import rag_lab` as the canonical Python namespace, and `rag-lab` as the canonical CLI.

**0.3.0 is PREPARED, not published.** Normal CI has no tag, release or package-publish step. See [Migration to 0.3](MIGRATION-0.3.md) for compatibility and rollback.

It keeps the complete trace from source contract to chunk, retrieval rank, claim, citation, and verdict. Invalid, expired, blocked, future-dated, or hash-mismatched sources are rejected fail-closed. Individual failures remain visible instead of disappearing behind aggregate scores.

## Quick start

For one complete corpus-to-evidence run, use an explicit suite and a new output directory:

```bash
rag-lab workflow --suite examples/suite.json --query "launch date" --output evidence-run-01
rag-lab verify-workflow --suite examples/suite.json --output evidence-run-01
```

This performs real retrieval and records exact source quotes, a verified index, the annotated benchmark, and a receipt linking their hashes. The bundled adversarial example intentionally fails the default 100% benchmark gate: exit code 1 preserves those failures. It does not generate an answer or infer confidence for the free query. See [the integrated workflow](docs/INTEGRATED-WORKFLOW.md) for input, replay, and exit-code contracts.

```bash
python -m pip install .
rag-lab validate --suite examples/suite.json
rag-lab run --suite examples/suite.json --output reports/demo.json
rag-lab verify --report reports/demo.json
rag-lab index --suite examples/suite.json --strategy hybrid --output reports/index.json
rag-lab sweep --suite examples/suite.json --strategies overlap,bm25,tfidf,hybrid --chunk-sizes 12,20 --overlaps 0,2 --output reports/sweep.json
rag-lab export --report reports/demo.json --format html --output reports/demo.html
rag-lab probe --level functional
```

Historical automation remains valid:

```bash
rag-quality-bench probe --level functional
python -c "import rag_quality_bench; print(rag_quality_bench.__version__)"
```

Canonical Python use:

```python
import rag_lab
print(rag_lab.__version__)
```

The example is synthetic and runs without a model account, network request, private corpus, or vector database.

## Evaluation surface

- recall@k, precision@k, reciprocal rank, and nDCG@k against expected source IDs
- claim groundedness using explicit cited evidence
- correct abstention on no-answer questions
- citation precision and recall against retrieved, trusted, fresh sources
- freshness coverage, adversarial pass rate, duplicates, pass rate, and measured retrieval latency
- seeded bootstrap confidence intervals for the benchmark pass rate
- semantic differences between two verified reports

Measured latency is reported but excluded from the semantic evidence SHA so the same logical result can be verified across clean machines.

New reports use report schema `2.0`, whose verifier checks nested records, aggregate metrics, the embedded index manifest, and all suite/index digest links. The loader remains backward-compatible with released schema `1.0` reports; legacy reports retain their original hash algorithm and are never silently rewritten.

## Retrieval strategies

- `overlap`: transparent query-token coverage baseline.
- `bm25`: bounded Okapi BM25 lexical ranking.
- `tfidf`: deterministic TF-IDF cosine ranking.
- `hybrid`: BM25 combined with a fixed-size feature-hashed vector score.

All strategies run locally with no model, service, embedding endpoint, or hidden state. The hybrid vector is deliberately a reproducible experimental baseline, not a semantic embedding model.

## Commands

Both `rag-lab` and the legacy `rag-quality-bench` expose the same command surface:

- `workflow` / `verify-workflow`: run and replay the integrated corpus, search, citation, and quality path in a new evidence directory.
- `validate`: validate the bounded versioned suite contract.
- `inventory`: show freshness, trust, hash status, and duplicate content.
- `run`: evaluate every question and optionally write an atomic verified report.
- `verify`: validate report structure and logical aggregates, enforce digest links, and recompute the semantic SHA.
- `compare`: show metric deltas and changed question outcomes.
- `index` / `verify-index`: write and verify a redacted index manifest that binds configuration and chunk hashes without publishing source text.
- `sweep`: compare at most 32 strategy/chunk configurations and select the best run by a documented deterministic score.
- `export`: turn a verified JSON report into safe Markdown or standalone HTML.
- `probe`: run separate liveness, readiness, or functional counter-proof checks.
- `demo`: run the bundled synthetic corpus and preserve the intentional failure.

Use `--minimum-pass-rate` with `run` to make CI fail when the report falls below an explicit gate.

## Release evidence

Flagship CI runs the root product on Ubuntu, Windows and macOS across CPython 3.11, 3.12 and 3.13. Every job builds wheel + sdist with the pinned build toolchain, installs the wheel, runs the full suite and functional counter-proof, smokes the installed CLI outside checkout, and executes the tests from the extracted sdist.

The release-evidence builder emits:

- `SHA256SUMS.txt` for wheel and sdist;
- CycloneDX 1.6 `rag-lab.cdx.json` with the distribution identity and hashes;
- `RELEASE_EVIDENCE.json` with source/runtime/platform metadata and explicit booleans showing the candidate is not tagged, published or released.

A separate manual-only workflow can generate and strictly verify GitHub/Sigstore SLSA provenance for an approved wheel. It uploads evidence but does not create a tag or GitHub Release. Publication and post-publication verification remain separate decisions.

## Public boundary

Only generic implementation code and synthetic `example.invalid` fixtures belong here. Do not add client names, private documents, credentials, internal topology, production URLs, or proprietary evaluation data. Index manifests intentionally contain source identifiers and hashes, so review those identifiers before publication. See [SECURITY.md](SECURITY.md), [docs/METHODOLOGY.md](docs/METHODOLOGY.md), and [AI_ASSISTANCE.md](AI_ASSISTANCE.md).

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python scripts/check.py
python -m pip install --upgrade -r requirements-build.txt
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist
python -c 'from setuptools.build_meta import build_sdist; print(build_sdist("dist"))'
python scripts/build_release_evidence.py --dist dist --output release-evidence
```

`requirements-build.txt` is the authoritative release toolchain. CI attests those exact versions before creating artifacts. The wheel is tested as the installed candidate rather than relying on imports from the checkout, and the complete source distribution is extracted and tested independently.

## Compatibility and rollback

The distribution name remains `rag-quality-bench` in 0.3 specifically to protect existing installation automation. Canonical and legacy Python namespaces/CLIs are tested together. Removing a historical alias requires a later migration with consumer evidence.

Rollback is documented in [MIGRATION-0.3.md](MIGRATION-0.3.md) and returns to the verified 0.2.0 artifact; 0.3 introduces no database or remote-state migration.

Licensed under Apache-2.0.
