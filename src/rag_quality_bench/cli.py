"""Bounded command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .engine import BenchmarkEngine, compare_reports
from .models import BenchmarkSuite, ContractError
from .probes import functional_probe, liveness_probe, readiness_probe
from .reporting import load_report, write_report


def _load_suite(path: str) -> BenchmarkSuite:
    target = Path(path)
    if not target.is_file():
        raise ContractError(f"suite does not exist: {target}")
    return BenchmarkSuite.from_json(target.read_text(encoding="utf-8"))


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rag-quality-bench")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate a versioned benchmark suite")
    validate.add_argument("--suite", required=True)
    run = commands.add_parser("run", help="run a benchmark and preserve all failures")
    run.add_argument("--suite", required=True)
    run.add_argument("--output")
    run.add_argument("--minimum-pass-rate", type=float)
    verify = commands.add_parser("verify", help="verify a written report")
    verify.add_argument("--report", required=True)
    compare = commands.add_parser("compare", help="diff two verified reports")
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--candidate", required=True)
    inventory = commands.add_parser("inventory", help="show trust, freshness, and duplicates")
    inventory.add_argument("--suite", required=True)
    probe = commands.add_parser("probe", help="run a health or counter-proof probe")
    probe.add_argument("--level", required=True, choices=["liveness", "readiness", "functional"])
    demo = commands.add_parser("demo", help="run the public synthetic example")
    demo.add_argument("--output", default="reports/demo.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            suite = _load_suite(args.suite)
            _print({
                "valid": True,
                "suite_id": suite.suite_id,
                "version": suite.version,
                "documents": len(suite.documents),
                "questions": len(suite.questions),
                "suite_sha256": suite.digest,
            })
            return 0
        if args.command == "run":
            if args.minimum_pass_rate is not None and not 0 <= args.minimum_pass_rate <= 1:
                raise ContractError("minimum pass rate must be between 0 and 1")
            report = BenchmarkEngine(_load_suite(args.suite)).run()
            if args.output:
                write_report(args.output, report)
            _print(report)
            return int(args.minimum_pass_rate is not None and report["metrics"]["pass_rate"] < args.minimum_pass_rate)
        if args.command == "verify":
            report = load_report(args.report)
            _print({"valid": True, "semantic_sha256": report["semantic_sha256"]})
            return 0
        if args.command == "compare":
            _print(compare_reports(load_report(args.baseline), load_report(args.candidate)))
            return 0
        if args.command == "inventory":
            _print(BenchmarkEngine(_load_suite(args.suite)).inventory())
            return 0
        if args.command == "probe":
            probes = {"liveness": liveness_probe, "readiness": readiness_probe, "functional": functional_probe}
            result = probes[args.level]()
            _print(result)
            return 0 if result["ok"] else 1
        if args.command == "demo":
            suite_path = Path(__file__).resolve().parents[2] / "examples" / "suite.json"
            if not suite_path.is_file():
                suite_path = Path("examples/suite.json")
            report = BenchmarkEngine(_load_suite(str(suite_path))).run()
            write_report(args.output, report)
            _print({
                "output": args.output,
                "metrics": report["metrics"],
                "failures_preserved": sum(len(row["failures"]) for row in report["records"]),
                "semantic_sha256": report["semantic_sha256"],
            })
            return 0
    except (ContractError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2

