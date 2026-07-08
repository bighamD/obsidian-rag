from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class EvalExample:
    question: str
    expected_source_files: list[str]
    id: str
    expected_answer_points: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvalDataset:
    examples: list[EvalExample]


def load_eval_dataset(path: Path) -> EvalDataset:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_examples = payload.get("examples", [])
    if not isinstance(raw_examples, list):
        raise ValueError("eval dataset must contain an examples list")

    examples: list[EvalExample] = []
    for index, raw_example in enumerate(raw_examples, start=1):
        if not isinstance(raw_example, dict):
            raise ValueError(f"example {index} must be a mapping")
        examples.append(_parse_example(raw_example, index))
    return EvalDataset(examples=examples)


def _parse_example(raw_example: dict[str, Any], index: int) -> EvalExample:
    question = str(raw_example.get("question", "")).strip()
    if not question:
        raise ValueError(f"example {index} is missing question")

    expected_source_files = _string_list(raw_example.get("expected_source_files"))
    if not expected_source_files:
        raise ValueError(f"example {index} is missing expected_source_files")

    example_id = str(raw_example.get("id") or f"example-{index}")
    return EvalExample(
        id=example_id,
        question=question,
        expected_source_files=expected_source_files,
        expected_answer_points=_string_list(raw_example.get("expected_answer_points")),
    )


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    raise ValueError("expected a string or list of strings")
