# Semantic Index Doctor

## Purpose

Fail-closed semantic vector index integrity diagnostics. The package is standard-library-only and designed for deterministic local use with synthetic or caller-controlled JSON.

## Non-goals

It does not repair vectors, inspect a remote index, or prove that embeddings are semantically useful.

## Install

Requires Python 3.11 or newer.

```bash
python -m pip install .
```

## CLI and API

Pass a JSON object by path or standard input. Success is emitted as machine-readable JSON; validation failures return exit status 2 without a traceback.

```bash
semantic-index-doctor examples/basic.json
python -m semantic_index_doctor.cli examples/basic.json
```

The public API is `semantic_index_doctor.core.run(data)`. Lower-level functions remain available for focused library use; inspect their signatures for supported keyword options.

## Example

The example diagnoses two finite, two-dimensional synthetic vectors.

```bash
semantic-index-doctor examples/basic.json
```

All example content is synthetic and safe to publish.

## Security and trust model

Entries and identifiers are structurally validated; dimensions are strict positive integers; booleans and non-finite components are rejected; duplicate, zero, and dimension defects block health.

The caller remains responsible for authenticating inputs and enforcing returned decisions at the real I/O or authorization boundary. Invalid and inconclusive inputs fail visibly rather than producing a healthy or verified claim.

## Limitations

The tool examines supplied JSON only and cannot attest to storage, model provenance, or remote index freshness.

## Tests

Run the full local contract:

```bash
python -m unittest discover -s tests -v
python scripts/check.py
python -m build --no-isolation
```

CI exercises Python 3.11 and 3.12, builds and installs the wheel, then runs tests, the public-boundary check, the module example, and the installed console command.

## AI assistance

AI-assisted contribution details and validation expectations are documented in [AI_ASSISTANCE.md](AI_ASSISTANCE.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).

