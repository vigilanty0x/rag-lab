# Explicit local file intake

This optional workflow input **replaces all inline documents** in the template
suite. There is no implicit merge, directory scan, deletion, automatic duplicate
selection, model call or source URL request. Existing questions and settings are
validated against the rebuilt suite. Missing or refused files fail the run;
they never become a healthy empty corpus.

## Runnable synthetic example

From the repository root, choose a new output directory whose parent exists:

```bash
rag-lab workflow --suite examples/intake-template.json --intake examples/intake-manifest.json --input-root examples/intake-files --query "launch city" --output intake-run-01
rag-lab verify-workflow --suite examples/intake-template.json --intake examples/intake-manifest.json --input-root examples/intake-files --output intake-run-01
```

The supplied text is a synthetic public handbook with Unicode and CRLF bytes.
The template's content date and evaluation date are declared fixture dates;
they do not assert current freshness. Workflow exit codes remain 0 for completed,
1 for an unmet quality gate or no results, and 2 for a refused input/operation.
Successful replay exits 0 even if the preserved original quality status failed.

## Python contract

```python
from rag_lab import BenchmarkSuite, load_intake, prepare_file_suite
from rag_lab import run_workflow, verify_workflow

template = BenchmarkSuite.from_json(template_json)
manifest = load_intake(manifest_path)
rebuilt, observation = prepare_file_suite(template, root=input_root, intake=manifest)
receipt = run_workflow(
    template, query="launch city", output=new_output_directory,
    root=input_root, intake=manifest, minimum_pass_rate=1.0, limit=None,
    previous_suite=None, vectors=None,
)
verified = verify_workflow(
    new_output_directory, template, root=input_root, intake=manifest,
    previous_suite=None, vectors=None,
)
```

`prepare_file_suite` reads the files and returns a canonical `BenchmarkSuite`
plus measured evidence without writing results. `run_workflow` performs its own
capture; it does not trust an earlier observation object. `root` must identify
the explicit local directory. Passing it without `intake` is refused. File
manifest JSON is loaded using a bounded loader which rejects duplicate keys
and non-finite constants. The manifest object is copied and normalized; later
caller mutations cannot change a capture in progress.

The manifest has exactly `schema_version: "rag-lab/file-intake-v1"` and `files`.
Each entry has exactly these fields:

| Field | Meaning |
| --- | --- |
| `name` | Normalized relative POSIX path under the explicit root |
| `size` | Expected original byte count; positive integer, never boolean |
| `sha256` | Lowercase SHA-256 of the original file bytes |
| `media_type` | `text/plain`, `text/markdown` or `application/json` |
| `source_id`, `title`, `source_url`, `license` | Existing canonical document metadata |
| `observed_at`, `expires_at`, `trust` | Existing declared content dates and trust |

Source IDs must be unique. Every document must satisfy the native document
contract, including the required observed date, ISO date formats and permitted
trust values. Future/expired/blocked/untrusted content is refused relative to
the template's explicit evaluation date. JSON media is read as UTF-8 text;
there is no JSON-to-document transformation.

Limits: 1–200 files, 800,000 bytes per file, 4,000,000 total input bytes,
512,000 serialized manifest bytes, 200,000 characters per document and the
native 5,000,000-byte suite bound. Paths are at most 512 characters/20 segments;
the root has at most 64 components. Case-insensitive aliases, traversal,
absolute names, Windows alternate streams/reserved names, control characters,
non-normalized names and common secret-file names/extensions are refused.
The filename checks are an additional bound, **not a secret detector**: the
caller must only authorize non-sensitive files. The CLI's template/manifest/
vector paths are explicit caller inputs; the confined reader applies to the
listed document files, not arbitrary files provided to those separate loaders.

## Bytes, boundaries and observations

Only regular singly-linked files are accepted. Root ancestors and document
parents are held open for the capture. POSIX reads use descriptor-relative
`O_NOFOLLOW` opens with type and identity checks. Windows uses read-only Win32
handles with reparse refusal and READ-only sharing; WRITE and DELETE sharing
are denied for both files and parent directories. Unsupported secure-reading
platforms and Windows UNC roots are refused. No permissions are changed.

Each list is read twice through the same pinned root. Size, hash and file
identity must remain equal across the capture. Parent substitution, links,
missing files and changed bytes are refused; Windows may physically prevent
the attempted replacement while handles are open. These are bounded local
file consistency checks, not an atomic filesystem snapshot or a guarantee
against a malicious privileged filesystem. Readers release their handles on
both success and refusal. There is no global cache or cross-thread state.

UTF-8 decoding preserves CRLF, spaces and Unicode. Canonical citation spans
remain Unicode character offsets, not byte offsets; original byte size and
SHA are recorded separately. Exact and whitespace/case-normalized duplicate
groups are diagnostics only. All listed documents remain present. A measured
capture does not mean the quality gate or duplicate diagnostics are healthy.

`file-observation.json` records a real UTC `read_at` for each first byte read,
separately from `observed_at_declared`, `expires_at_declared`, and
`trust_declared`. Content date and source provenance remain caller declarations;
`source_origin_verified` is false. The absolute root is not persisted. Relative
names, source metadata, reconstructed content, queries and quotes are present
in the evidence; this is an explicit content export.

## Receipts, supplied vectors and replay

Intake runs use `rag-lab/workflow-v4` and add `intake.json`, `suite.json` and
`file-observation.json` to the normal artifacts. The receipt binds the template,
rebuilt suite, manifest, observation and each artifact. Existing v1/v2/v3 runs
without intake retain their schemas and behavior. `--previous-suite` compares
that explicit prior suite with the rebuilt corpus, using the existing diff.

Supplied vectors can be combined with intake. Select `supplied` in the template,
prepare the reconstructed suite, and provide vectors bound to **that exact suite
digest**, its chunk IDs/text hashes, and all annotated/free queries. Vectors for
the template's replaced inline documents are refused. Both Python functions
accept the existing `vectors=<payload or SuppliedVectors>` argument; CLI uses
`--vectors`. No embedding generation or model origin is inferred.

Replay requires the same explicit template, manifest, files and optional vector
or previous-suite inputs. It re-reads bytes, reconstructs the suite and recomputes
retrieval, citations, quality and artifact links. Re-hashing a tampered artifact
alone is insufficient. Files may be relocated under another authorized root if
the relative list and bytes are identical. Identities detect changes within a
capture; they are not a persistent binding to the original inode or Windows ID.

Replay preserves the original recorded `read_at` instead of rewriting history.
It checks its format and rejects future timestamps, but cannot authenticate a
past timestamp if someone forges all hashes consistently. Neither unsigned
receipts nor declared provenance prove authorship. Call `prepare_file_suite`
separately when a fresh observation timestamp is needed.

## Refusals and source parity

`IntakeError` is a `ContractError` with `.code` and optional relative `.name`.
Useful codes include `ROOT_REQUIRED`, `INVALID_ROOT`,
`ROOT_UNAVAILABLE_OR_UNSAFE`, `INVALID_PATH`, `FORBIDDEN_PATH`, `FILE_MISSING`,
`FILE_UNAVAILABLE_OR_UNSAFE`, `NON_REGULAR_OR_LINKED`, `SOURCE_CHANGED`,
`FILE_COUNT_LIMIT`, `INVALID_FILE_SIZE`, `FILE_BYTE_LIMIT`, `TOTAL_BYTE_LIMIT`,
`MANIFEST_BYTE_LIMIT`, `SUITE_BYTE_LIMIT`, `SIZE_MISMATCH`, `HASH_MISMATCH`,
`INVALID_UTF8`, `INVALID_DOCUMENT_METADATA`, `INVALID_DOCUMENT_CONTENT`,
`REBUILT_SUITE_INVALID`, `DECLARED_CONTENT_REFUSED_*`,
`INTAKE_OBSERVATION_MISMATCH` and `READ_TIMESTAMP_IN_FUTURE`.
Ordinary canonical workflow/vector errors remain `ContractError`. No output
directory is created for a capture/validation refusal. An interrupted output
write keeps its partial artifacts and cannot pass normal replay.

Parity tests call the retained `file_intake_pipeline.intake`,
`rag_corpus_doctor.evaluate`, `data_freshness_monitor.monitor` and
`rag_citation_explorer.build_citation_view` functions directly. Duplicate groups
are compared to the actual retained `duplicate_finder.find` source, frozen with
its source SHA in the test oracle. These sources have different scopes: metadata
validation, count diagnostics, declared-date classification and citation
checking. The canonical engine's existing ranking and grounding rules remain
unchanged; none of these small tools replaces the engine with an imitation.
