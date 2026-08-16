# Data Freshness Monitor

## Purpose

Deterministic freshness decisions for timestamped datasets. The package is standard-library-only and designed for deterministic local use with synthetic or caller-controlled JSON.

## Non-goals

It does not fetch datasets, read a wall clock implicitly, or prove data quality or completeness.

## Install

Requires Python 3.11 or newer.

```bash
python -m pip install .
```

## CLI and API

Pass a JSON object by path or standard input. Success is emitted as machine-readable JSON; validation failures return exit status 2 without a traceback.

```bash
data-freshness-monitor examples/basic.json
python -m data_freshness_monitor.cli examples/basic.json
```

The public API is `data_freshness_monitor.core.run(data)`. Lower-level functions remain available for focused library use; inspect their signatures for supported keyword options.

## Example

The example compares one synthetic UTC observation with an explicit UTC evaluation time.

```bash
data-freshness-monitor examples/basic.json
```

All example content is synthetic and safe to publish.

## Security and trust model

The caller must supply an explicit aware now timestamp. Dataset IDs, timestamps, age limits, and aggregate counts are validated; future timestamps are reported separately with nonnegative age evidence.

The caller remains responsible for authenticating inputs and enforcing returned decisions at the real I/O or authorization boundary. Invalid and inconclusive inputs fail visibly rather than producing a healthy or verified claim.

## Limitations

Freshness is only elapsed-time evidence. Clock provenance and acceptable skew remain caller policy.

## Tests

Run the full local contract:

```bash
python -m unittest discover -s tests -v
python scripts/check.py
python -m build --no-isolation
```

CI exercises Python 3.11 and 3.12, builds and installs the wheel, then runs tests, the public-boundary check, the module example, and the installed console command.

## AI assistance

AI-assisted contribution details and validation expectations are documented in [AI_ASSISTANCE.md](AI_ASSISTANCE.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).

