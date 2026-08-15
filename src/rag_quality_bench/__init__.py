"""Public API for RAG Quality Bench."""

from .engine import BenchmarkEngine, evaluate_suite
from .models import BenchmarkSuite, ContractError

__all__ = ["BenchmarkEngine", "BenchmarkSuite", "ContractError", "evaluate_suite"]
__version__ = "0.1.0"

