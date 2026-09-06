# Supplied vectors: explicit offline input

RAG Lab accepts externally supplied numbers through the existing workflow. It
does not generate embeddings, contact a provider, load a model, follow source
URLs, or authenticate the declared model/version/provenance. The bundled
example contains manually specified synthetic vectors, not a model benchmark.

## Run and replay

```bash
rag-lab workflow --suite examples/supplied-suite.json --vectors examples/supplied-vectors.json --query "launch café a" --minimum-pass-rate 0 --output supplied-run-01
rag-lab verify-workflow --suite examples/supplied-suite.json --vectors examples/supplied-vectors.json --output supplied-run-01
rag-lab export --report supplied-run-01/report.json --format html --output supplied-run-01.html
```

The example's zero quality threshold is explicit and only exercises the
workflow; it is not a recommended business acceptance threshold. The default
threshold remains 1.0, and annotated failures remain in every report.

The suite must explicitly declare `retrieval_strategy: "supplied"`. Its
`hybrid_weight` is the lexical weight in `[0, 1]`: zero gives cosine-only
ranking; one gives lexical-frequency ranking while still requiring complete,
valid vectors. No fallback occurs if the payload or a query vector is missing.
`run` and `index` also accept `--vectors`. If using `--strategy supplied` on
these commands, the payload's suite digest must correspond to the resulting
suite after that override. `workflow` uses the strategy in its suite directly.

The four original strategies, default suites, index-v1 and workflow-v1/v2
receipts are unchanged. In particular, `hybrid` still means feature hashing,
not this supplied-vector mode. A supplied run writes index-v2 and workflow-v3.
`sweep` has no vectors input: requesting `supplied` is refused, because changed
chunk sizes would require newly bound vectors for each candidate suite.

## Python and future CC adapter

```python
from rag_lab import BenchmarkSuite, load_vectors, run_workflow, verify_workflow

suite = BenchmarkSuite.from_json(suite_text)
vectors = load_vectors(explicit_local_vectors_path)
receipt = run_workflow(
    suite, query="launch café a", output=new_output_directory,
    vectors=vectors, minimum_pass_rate=1.0, limit=None, previous_suite=None,
)
verified = verify_workflow(new_output_directory, suite, vectors=vectors,
                           previous_suite=None)
```

Both functions accept `vectors: dict | SuppliedVectors | None`. A dictionary
is fully validated. A `SuppliedVectors` instance is also revalidated from its
bounded serialized snapshot; caller-constructed maps do not bypass validation.
`BenchmarkEngine(suite, vectors=payload)` is the lower-level common engine;
its `.vectors` property contains the immutable validated snapshot.

For a CC adapter, select the canonical suite and exact free query first, obtain
the explicit payload, then call this API in the adapter's already confined
workspace. This library's CLI is an explicit local-file interface; it does not
provide an HTTP path allowlist or an authorization policy for arbitrary file
paths. There is no shell or network capability in these functions.

On an input/refusal error, `ContractError` is raised before creation of the
output directory. The CLI returns 2 for contract/I/O errors, 1 for a completed
workflow whose status is `quality_failed` or `no_results`, and 0 for `completed`.
An I/O interruption after writing starts preserves partial artifacts without
a completion receipt. An existing output directory is never reused.

## Payload version 1

See the complete, executable [synthetic payload](../examples/supplied-vectors.json)
and its [suite](../examples/supplied-suite.json). Exact object fields:

| Object | Required fields |
| --- | --- |
| Root | `schema_version`, `suite_sha256`, `model`, `model_version`, `dimension`, `provenance`, `chunks`, `queries` |
| Provenance | `kind: "caller_declared"`, `reference`, `artifact_sha256` |
| Every chunk/query row | `id`, `text_sha256`, `model`, `model_version`, `vector` |

`schema_version` is `rag-lab/vectors-v1`. Digests are lowercase, 64-character
SHA-256. `suite_sha256` is `suite.digest`, not the hash of a formatted suite
file. Model/version must be nonempty UTF-8 strings, at most 256 bytes, and
must match exactly on every row. Provenance reference is nonempty and at most
1024 bytes; it is recorded without opening it. Its artifact digest is also a
declaration, not a measurement of that external artifact.

Chunk rows cover exactly the chunks from documents accepted by the suite's
existing trust/freshness/content-hash rules. Chunk IDs are those of the existing
`chunk_document` engine (`source_id:ordinal:start-end`); `text_sha256` hashes
the normalized chunk text's exact UTF-8 bytes. No document vector is silently
reused for several chunks. The existing index command on an otherwise
identical lexical suite can show IDs/text hashes; the vectors payload must
still bind the final supplied-mode suite digest.

Query row `id` and `text_sha256` both equal the SHA-256 of the exact UTF-8 query
text. All annotated question texts and the free query must be covered. Repeated
identical question texts share one row. Duplicate query rows are refused even
when their values agree. Extra query rows are permitted within the bounds, so
several explicit free queries can share one payload. Whitespace, case and
Unicode changes require a different query row; there is no inferred embedding.

Bounds: 32 MiB input/canonical artifact, 1,000,000 scalars across both groups,
1–4096 dimensions, 1–10,000 chunk rows and 1–1001 query rows. IDs are at most
256 UTF-8 bytes. Every vector has the exact declared dimension. Booleans,
NaN/Inf, unrepresentable integer components, zero norms and nonfinite norms
are refused. Zero cosine is valid; a zero vector is not. Unknown fields,
duplicate JSON keys/IDs, missing chunks/queries, mismatched text hashes and
mixed models/versions are rejected before construction of the retrieval index.

## Scoring and actual source parity

The supplied strategy ports the retained
`packages/hybrid-search-playground/src/hybrid_search_playground/core.py:search`:
Unicode `\w+` tokens, case-folding, unique query terms, term frequency divided
by chunk-token count, then `weight * lexical + (1 - weight) * cosine`.
Cosine uses `math.hypot` and divides before products, avoiding overflow from
squaring large finite coordinates. It is clamped to `[-1, 1]`. Ranking keeps
signed and zero scores and sorts ties by chunk ID, exactly as that source.
These rank results do not by themselves mean that a relevant answer exists.

The other canonical strategies retain their original positive-score filter
and original lexical/BM25/TF-IDF/feature-hash calculations. The new strategy's
`score_kind` is `supplied_cosine_rank` for weight zero, otherwise
`lexical_frequency_and_supplied_cosine_rank`. `confidence` remains null and
query quality remains `not_measured`; `embedding_model` contains declared
model/version/dimension/provenance, the vectors digest, `origin_verified: false`
and `provider_called: false`.

Validation preserves the actual `semantic_index_doctor.diagnose` refusals for
dimension, duplicates, nonfinite components and zero vectors, adding space,
hash and aggregate-size constraints absent from that source. The retained
`embedding_lab.evaluate` only validates positive dimension/count declarations;
it is not an embedding engine and does not prove a model was run. Tests call
these retained functions directly as parity oracles. No source-package loader
is used in the production workflow.

## Evidence and verification limits

`vectors.json` records the validated input in canonical indented JSON. Its
semantic digest is bound into the index, search, report and workflow receipt;
its exact bytes are also hashed in the receipt's artifact table. Version 3 can
include the existing optional `corpus-diff.json`, requiring the same explicit
previous suite at replay.

`verify-workflow` requires the caller's same vectors input. It compares the
recorded artifact to that validated snapshot and recomputes index, search,
citations and benchmark evidence. Merely rehashing an altered artifact does
not satisfy replay. The standalone `verify`/`verify-index` commands check
structure, internal links and self-hashes; only workflow replay checks against
the explicit suite and vectors. Replacing every input and every receipt is
not publisher authentication. Model origin and vector meaning remain unproved.

Reports retain schema 2.0; their validator accepts signed bounded scores only
when the manifest uses the explicit supplied strategy and valid index-v2 vector
metadata. Old external consumers that only understand index-v1 must refuse
this opt-in mode until updated. Markdown/HTML exports show the mode and state
the model/provenance limitations; default-mode exports remain byte-compatible.
