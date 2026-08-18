# Changelog

## 0.3.0 - 2026-08-18

- Make **RAG Lab** the canonical product identity while preserving the released `rag-quality-bench` distribution and CLI as compatibility surfaces.
- Add canonical `rag_lab` Python namespace, `python -m rag_lab`, and `rag-lab` CLI; all canonical and legacy surfaces report version `0.3.0`.
- Expand flagship CI to Ubuntu, Windows, and macOS across CPython 3.11, 3.12, and 3.13.
- Build wheel and sdist on every matrix job, install the built wheel, smoke the installed CLI outside the checkout, run the functional counter-proof, and test the complete sdist.
- Generate bounded release evidence with SHA-256 checksums, CycloneDX 1.6 SBOM, platform/runtime metadata, and an explicit `PREPARED` state that cannot be mistaken for publication.
- Add a manual-only provenance workflow that rebuilds an approved candidate, verifies it, generates release evidence, signs the wheel with GitHub/Sigstore SLSA provenance, strictly verifies the attestation, and uploads the candidate bundle without creating a tag or release.
- Document identity migration, compatibility, release gates, rollback to 0.2.0, and the requirement for separate publication/post-publication verification before any archival decision.

`0.3.0` is a prepared candidate. No tag, GitHub Release, package publication, source-repository archive, or deletion is implied by this changelog entry.

## 0.2.0 - 2026-08-16

- Add deterministic overlap, BM25, TF-IDF, and hybrid retrieval backends.
- Add precision@k, reciprocal rank, nDCG@k, citation precision/recall, adversarial pass rate, and seeded pass-rate confidence intervals.
- Add redacted, self-verifying index manifests bound to suite, strategy, chunks, and source hashes.
- Add bounded configuration sweeps with deterministic run IDs and best-run selection.
- Add safe Markdown and standalone HTML evidence exports.
- Bind report identity into the semantic hash, reject unknown report fields and duplicate JSON keys, and strictly validate self-hashed manifest structure.
- Add CLI coverage for indexing, index verification, sweeps, exports, and per-run strategy selection.
- Pin CI actions to immutable commits and exercise the release artifact plus new end-to-end paths.
- Bundle the synthetic demo inside the wheel, reject duplicate manifest keys, and enforce input limits before unbounded allocation.
- Version new evidence as report schema 2.0 while retaining a backward-compatible schema 1.0 loader, hash verifier, and legacy default-suite digests.
- Deeply verify nested reports, aggregate metrics, retrieved text, embedded manifests, and all suite/index digest links before atomic replacement.
- Require citation evidence to be expected, valid, and retrieved; reject duplicate expected-source IDs and extreme numeric inputs with bounded errors.
- Preflight the 100,000-chunk ceiling, cap sweep dimensions before enumeration, and stop generic index iterables at their consumption bound.
- Ship complete, testable source distributions and build wheel/sdist with an attested pinned toolchain in least-privilege CI.

## 0.1.0 - 2026-08-15

- Add bounded source, suite, question, response, and claim contracts.
- Add deterministic chunking and transparent lexical retrieval.
- Add citation, groundedness, no-answer, recall, freshness, and latency evaluation.
- Add atomic evidence reports, semantic SHA verification, and report comparison.
- Add separate liveness, readiness, and functional counter-proof probes.
