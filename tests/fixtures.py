from __future__ import annotations

from copy import deepcopy

from rag_quality_bench.models import BenchmarkSuite, content_sha256


def suite_dict() -> dict:
    content = "The public handbook says the launch city is Geneva and the launch color is teal."
    return {
        "schema_version": "1.0",
        "suite_id": "unit-suite",
        "version": "1.2.3",
        "evaluation_date": "2026-08-15",
        "chunk_size": 12,
        "chunk_overlap": 2,
        "retrieval_k": 3,
        "documents": [{
            "source_id": "handbook",
            "title": "Public handbook",
            "source_url": "https://example.invalid/handbook",
            "license": "CC0-1.0",
            "observed_at": "2026-08-14",
            "expires_at": "2027-08-14",
            "trust": "trusted",
            "content": content,
            "sha256": content_sha256(content),
        }],
        "questions": [
            {
                "question_id": "launch-city",
                "text": "What is the launch city?",
                "expected_source_ids": ["handbook"],
                "no_answer": False,
                "adversarial": False,
                "response": {
                    "answer": "The launch city is Geneva.",
                    "claims": [{"text": "launch city is Geneva", "citations": ["handbook"]}],
                },
            },
            {
                "question_id": "unknown-owner",
                "text": "Who owns the invisible submarine?",
                "expected_source_ids": [],
                "no_answer": True,
                "adversarial": True,
                "response": {"answer": None, "claims": []},
            },
        ],
    }


def suite() -> BenchmarkSuite:
    return BenchmarkSuite.from_dict(deepcopy(suite_dict()))


class StepClock:
    def __init__(self, step: int):
        self.value = 0
        self.step = step

    def __call__(self) -> int:
        current = self.value
        self.value += self.step
        return current

