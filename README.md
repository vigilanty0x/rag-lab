# RAG Citation Explorer

## Purpose

Distinguish structural citation coverage from conservative semantic support using a trusted source/chunk registry, stable IDs, exact text digests, and exact quote spans.

## Non-goals

The package does not retrieve sources, decide broad entailment, authenticate the registry, or call a merely linked claim verified.

## Install

Requires Python 3.11 or newer: `python -m pip install .`

## API

`evaluate(record)` accepts `answer`, claims, registered sources/chunks, and citations with `quote`, `start`, and `end`. Support requires an exact registered span and every normalized claim token in the quote.

## CLI

Run `rag-citation-explorer examples/valid.json` to inspect both coverage measures.

## Example

The example includes the SHA-256 digest of its synthetic chunk and an exact supporting quote span.

## Security

Unknown IDs, duplicate chunks, digest mismatch, bad spans, unsupported claims, non-finite JSON, excessive counts, and oversized text fail closed. Failed semantic checks retain the structured view.

## Limits

The deterministic token rule is intentionally conservative and is not a general semantic-entailment model. Aggregate input is capped at 256 KiB.

## Tests

Run `python -m unittest discover -s tests -v` and `python scripts/check.py`.

## AI assistance

See `AI_ASSISTANCE.md`; source trust and nuanced support require human review.

## License

Apache-2.0; see `LICENSE`.
