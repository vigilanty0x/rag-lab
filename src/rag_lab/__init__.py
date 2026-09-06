"""Canonical Python namespace for RAG Lab.

The implementation reuses the proven ``rag_quality_bench`` evaluation engine.
The legacy namespace remains supported during the 0.3 identity migration.
"""

__version__ = "0.3.0"

from rag_quality_bench import BenchmarkEngine, BenchmarkSuite, ContractError, evaluate_suite
from rag_quality_bench.workflow import run_workflow, verify_workflow
from rag_quality_bench.supplied_vectors import SuppliedVectors, load_vectors
from rag_quality_bench.file_intake import prepare_file_suite, load_intake
from rag_quality_bench.intake_io import IntakeError

__all__ = [
    "BenchmarkEngine",
    "BenchmarkSuite",
    "ContractError",
    "evaluate_suite",
    "run_workflow",
    "verify_workflow",
    "SuppliedVectors",
    "load_vectors",
    "prepare_file_suite",
    "load_intake",
    "IntakeError",
    "__version__",
]
