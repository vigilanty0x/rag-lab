# Security Policy

## Supported versions

Security fixes target the latest release.

## Reporting

Report vulnerabilities privately through GitHub's security reporting flow. Do not open a public issue containing exploit details or sensitive data.

## Security model

- Input JSON is size-bounded and schema-validated.
- Source content is accepted only when its SHA-256, trust, and freshness checks pass.
- Unknown fields fail validation to expose schema drift.
- Reports are written atomically and verified after reopening.
- The runtime performs no network requests and executes no corpus content.

This tool is an evaluation aid, not a sandbox for hostile files. Keep untrusted datasets outside privileged environments.

