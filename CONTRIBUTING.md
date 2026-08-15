# Contributing

Contributions must stay generic, offline, reproducible, and free of private data.

1. Add or update a public contract test.
2. Implement the smallest coherent change.
3. Run `PYTHONPATH=src python -m unittest discover -s tests -v`.
4. Run `PYTHONPATH=src python scripts/check.py`.
5. Explain schema, metric, and compatibility changes in the pull request.

Fixtures must be synthetic and use reserved domains such as `example.invalid`. Never commit credentials, client content, proprietary corpora, or production endpoints.

