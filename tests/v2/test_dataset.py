from pathlib import Path

from obsidian_rag.v2.evaluation.dataset import load_eval_dataset


def test_load_eval_dataset_reads_yaml_examples(tmp_path: Path):
    dataset_path = tmp_path / "eval_set.yaml"
    dataset_path.write_text(
        """
examples:
  - id: chicken-wash
    question: 生鸡肉要不要洗？
    expected_source_files:
      - food.md
    expected_answer_points:
      - 不建议冲洗生鸡肉
  - question: 鸡肉安全温度是多少？
    expected_source_files:
      - temperature.md
""".strip(),
        encoding="utf-8",
    )

    dataset = load_eval_dataset(dataset_path)

    assert dataset.examples[0].id == "chicken-wash"
    assert dataset.examples[0].question == "生鸡肉要不要洗？"
    assert dataset.examples[0].expected_source_files == ["food.md"]
    assert dataset.examples[0].expected_answer_points == ["不建议冲洗生鸡肉"]
    assert dataset.examples[1].id == "example-2"
    assert dataset.examples[1].expected_answer_points == []
