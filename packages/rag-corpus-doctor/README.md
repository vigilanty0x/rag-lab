# RAG Corpus Doctor

Detect missing, duplicate, and stale corpus entries.

## Quick start

```bash
python -m pip install -e .
rag-corpus-doctor record.json
```

The CLI emits deterministic fail-closed JSON plus a SHA-256 evidence identifier. Required fields: `documents`, `indexed`, `duplicates`. Rule: all documents must be indexed with no duplicates.

## Verify

```bash
python -m unittest discover -s tests -v
python scripts/check.py
```

Apache-2.0. Python 3.11+. Zero runtime dependencies.

