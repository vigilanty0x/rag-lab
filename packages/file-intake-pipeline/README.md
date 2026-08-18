# File Intake Pipeline

## Purpose

Validate bounded synthetic file metadata and produce a canonical SHA-addressed intake manifest.

## Non-goals

It does not open, upload, scan, quarantine, or persist file bytes.

## Install

Requires Python 3.11 or newer.

```console
python -m pip install .
```

## CLI and API

Run the built-in positive and negative control:

```console
file-intake probe
```

Process JSON from a file:

```console
file-intake intake --input examples/basic.json
```

The public Python seam is `file_intake_pipeline.intake`:

```python
from file_intake_pipeline import intake
```

Functions return structured JSON-compatible results and reject malformed input without raising validation exceptions.

## Example

A runnable input is provided at `examples/basic.json`. CLI output is deterministic and includes either a SHA-256 evidence field or an explicit validation failure.

## Security and trust model

All manifest fields are untrusted. Only normalized relative names, allowlisted media types, lowercase SHA-256 values, and strict non-boolean sizes are accepted. The tool performs no network calls.

## Limitations

At most 1,000 entries and 1 GB of declared aggregate bytes are supported; digest claims are metadata and are not recomputed from file content.

## Tests

Run the same local gates used by CI:

```console
python -m unittest discover -s tests -v
python scripts/check.py
python -m build --no-isolation
file-intake probe
file-intake intake --input examples/basic.json
```

CI tests Python 3.11 and 3.12, installs the project and rebuilt wheel, imports the installed package, and exercises both the probe and example.

## AI disclosure

AI assistance supported defensive implementation, adversarial test design, and documentation. See [AI_ASSISTANCE.md](AI_ASSISTANCE.md) for scope and review expectations.

## License

Apache-2.0. See [LICENSE](LICENSE).

