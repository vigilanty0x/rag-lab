# Dataset Versioner

## Purpose

Canonical JSON dataset hashes with added, removed, and changed row evidence. The package is standard-library-only and designed for deterministic local use with synthetic or caller-controlled JSON.

## Non-goals

It does not store datasets, sign versions, merge changes, or infer stable identifiers.

## Install

Requires Python 3.11 or newer.

```bash
python -m pip install .
```

## CLI and API

Pass a JSON object by path or standard input. Success is emitted as machine-readable JSON; validation failures return exit status 2 without a traceback.

```bash
dataset-versioner examples/basic.json
python -m dataset_versioner.cli examples/basic.json
```

The public API is `dataset_versioner.core.run(data)`. Lower-level functions remain available for focused library use; inspect their signatures for supported keyword options.

## Example

The example compares two small synthetic dataset revisions.

```bash
dataset-versioner examples/basic.json
```

All example content is synthetic and safe to publish.

## Security and trust model

Rows must be bounded finite JSON objects with unique identifiers after serialization. Canonical encoding and aggregate byte ceilings prevent ambiguous or unbounded hashing.

The caller remains responsible for authenticating inputs and enforcing returned decisions at the real I/O or authorization boundary. Invalid and inconclusive inputs fail visibly rather than producing a healthy or verified claim.

## Limitations

A digest proves equality under this canonicalization only; it does not authenticate the dataset source.

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

