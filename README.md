# Semantic Index Doctor

Fail-closed semantic vector index integrity diagnostics.

Public offline Python MVP using only the standard library. Inputs are bounded, failures remain visible, and all examples/tests use synthetic data.

## CLI

```bash
python -m semantic_index_doctor.cli input.json
python -m unittest discover -s tests -v
python scripts/check.py
```

The public Python API is `semantic_index_doctor.core.run(data)`. The CLI accepts the same JSON object from a path or standard input and emits machine-readable JSON.

Apache License 2.0.

