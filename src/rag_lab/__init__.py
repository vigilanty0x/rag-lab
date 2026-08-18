"""Canonical Python namespace for RAG Lab.

The implementation reuses the proven ``rag_quality_bench`` evaluation engine.
The legacy namespace remains supported during the 0.3 identity migration.
"""

__version__ = "0.3.0"

from rag_quality_bench import BenchmarkEngine, BenchmarkSuite, ContractError, evaluate_suite

__all__ = [
    "BenchmarkEngine",
    "BenchmarkSuite",
    "ContractError",
    "evaluate_suite",
    "__version__",
]
