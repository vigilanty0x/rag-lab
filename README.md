# RAG Quality Bench

RAG Quality Bench is a dependency-free, offline framework for evaluating retrieval, citations, groundedness, no-answer behavior, freshness, and index drift on versioned public datasets.

It keeps the full trace from source contract to chunk, retrieval, claim, and evidence. Invalid, expired, blocked, or hash-mismatched sources are rejected fail-closed. Failures stay in the report instead of disappearing behind aggregate scores.

## Quick start

```bash
python -m pip install .
rag-quality-bench validate --suite examples/suite.json
rag-quality-bench run --suite examples/suite.json --output reports/demo.json
rag-quality-bench verify --report reports/demo.json
rag-quality-bench probe --level functional
```

The example is synthetic and runs without a model account, network request, private corpus, or vector database.

## What it measures

- retrieval recall@k against expected public source IDs
- claim groundedness using explicit cited evidence
- correct abstention on no-answer questions
- citation validity against retrieved, trusted, fresh sources
- freshness coverage, duplicates, pass rate, and measured retrieval latency
- semantic differences between two verified reports

Measured latency is reported but excluded from the semantic evidence SHA so the same logical result can be verified across clean machines.

## Commands

- `validate`: validate the bounded versioned suite contract.
- `inventory`: show freshness, trust, hash status, and duplicate content.
- `run`: evaluate every question and optionally write an atomic verified report.
- `verify`: recompute and verify a report's semantic SHA.
- `compare`: show metric deltas and changed question outcomes.
- `probe`: run separate liveness, readiness, or functional counter-proof checks.
- `demo`: run the bundled synthetic corpus and preserve the intentional failure.

Use `--minimum-pass-rate` with `run` to make CI fail when the report falls below an explicit gate.

## Public boundary

Only generic implementation code and synthetic `example.invalid` fixtures belong here. Do not add client names, private documents, credentials, internal topology, production URLs, or proprietary evaluation data. See [SECURITY.md](SECURITY.md), [docs/METHODOLOGY.md](docs/METHODOLOGY.md), and [AI_ASSISTANCE.md](AI_ASSISTANCE.md).

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python scripts/check.py
PIP_NO_INDEX=1 python -m pip wheel . --no-deps --no-build-isolation
```

Licensed under Apache-2.0.

