# Embedding Lab

Validate embedding dimensions, counts, and reproducible evidence.

## Quick start

```bash
python -m pip install -e .
embedding-lab record.json
```

The CLI emits deterministic fail-closed JSON plus a SHA-256 evidence identifier. Required fields: `model`, `dimensions`, `vector_count`. Rule: dimensions and vector count must be positive.

## Verify

```bash
python -m unittest discover -s tests -v
python scripts/check.py
```

Apache-2.0. Python 3.11+. Zero runtime dependencies.

