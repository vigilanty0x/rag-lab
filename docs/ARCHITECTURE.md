# Architecture

The dependency direction is deliberately small:

1. `models` validates versioned, bounded public contracts.
2. `engine` rejects invalid sources, chunks valid content, builds a deterministic index, retrieves, and evaluates claims.
3. `reporting` writes an atomic report and verifies its semantic SHA.
4. `probes` proves process health separately from real functional behavior.
5. `cli` exposes stable commands without embedding provider credentials or network clients.

Every retrieved chunk carries its source ID, document SHA, ordinal, and text. Every claim lists explicit source citations. Aggregate metrics are derived from retained question records.

