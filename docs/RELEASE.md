# RAG Lab release contract

RAG Lab separates candidate quality from publication state. A successful test, build, SBOM, checksum, or provenance step is evidence for a candidate; none of those observations means a release exists.

## States

- `PREPARED`: source SHA has reproducible candidate artifacts and required quality evidence.
- `ATTESTED`: an approved candidate wheel has GitHub/Sigstore provenance that was independently verified against repository/workflow/ref/SHA policy.
- `TAGGED`: an explicit immutable release tag has been created after approval.
- `RELEASED`: expected artifacts were published under that tag.
- `VERIFIED`: a separate read-back has verified tag target, assets, SHA-256 checksums, SBOM/provenance linkage, installability and smoke behavior.
- `BLOCKED`: one or more required gates are missing or red.
- `ROLLED_BACK`: a published candidate was superseded by the documented last-known-good 0.2.0 path.

Normal pull-request CI for 0.3 can establish `PREPARED` and signed provenance evidence. `release-policy.v1.json` has `publish_enabled=false`, so it cannot establish `TAGGED`, `RELEASED`, or `VERIFIED`.

## Required pre-publication evidence

1. Root product on Ubuntu, Windows and macOS across CPython 3.11-3.14.
2. Every imported package built and tested on Ubuntu across its supported CPython 3.11-3.12 versions.
3. Wheel and source distribution built by the pinned toolchain.
4. Full unit suite against the installed wheel.
5. Canonical and legacy identity compatibility.
6. Functional probe with intentional counter-example preserved.
7. Installed CLI smoke outside checkout.
8. Tests executed from the complete source distribution.
9. SHA-256 checksums and CycloneDX 1.6 SBOM.
10. Verified GitHub/Sigstore SLSA provenance on the approved wheel, only after root and imported-package CI pass.
11. Consumer/redirect review and explicit publication decision.

## Publication gate

A future publication change must be separate and reviewed. It must name the exact source SHA, re-enable publication explicitly, document immutable asset names, retain rollback, and add a read-only post-publication verifier. It must not infer `RELEASED` from the existence of a tag or workflow success alone.

## Rollback

The 0.3 migration is code/package identity only. No database or remote-state transformation exists. The rollback target is 0.2.0 using the historical `rag-quality-bench` distribution/CLI and `rag_quality_bench` namespace.

If a future 0.3 publication fails post-publication verification, stop further publication, preserve the failed evidence, restore consumers to the verified 0.2.0 artifact as needed, and record the release incident rather than deleting evidence to obtain a green status.

## Archive gate

The consolidated source repositories remain unarchived until a separate human decision after consumer inventory, compatibility/redirect proof and rollback verification. Repository consolidation alone is not an archive authorization.
