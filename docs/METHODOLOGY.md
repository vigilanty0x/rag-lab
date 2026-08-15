# Methodology

## Fair comparisons

Compare suites with the same questions, retrieval `k`, evaluation date, and source contracts. Record every configuration change. A different chunk size or corpus produces a different suite or index SHA and should be reviewed as a distinct candidate.

## Judges

- Retrieval recall uses expected source IDs.
- Citation validity requires cited sources to be valid and present in retrieval results.
- Groundedness requires at least 75 percent claim-token coverage in cited source content.
- No-answer accuracy compares explicit abstention with the question contract.

These transparent lexical rules are intentionally limited. Token overlap does not prove semantic entailment. Results must report that limitation and preserve adversarial failures.

## Reproducibility

Latency depends on the machine, so it is reported but excluded from the semantic SHA. All logical records, source hashes, retrieval results, and non-latency metrics are verified.

