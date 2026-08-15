# Suite Schema 1.0

A suite declares a semantic version, fixed evaluation date, chunk configuration, retrieval `k`, source contracts, questions, and candidate responses.

Each document requires source ID, URL, license, observed date, trust state, content, and SHA-256. Optional expiration makes freshness deterministic.

Each answerable question requires expected source IDs and a response with one or more claims. Each claim requires explicit source citations. A no-answer question expects no source and an abstaining response.

Limits: 200 documents, 500 questions, 200,000 characters per document, chunk size 8-500, and retrieval `k` 1-20.

