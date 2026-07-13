from obsidian_rag.v3_9.evaluation.dataset import load_agent_eval_dataset


def test_load_agent_eval_dataset_parses_agent_request_and_expectations(tmp_path):
    dataset_path = tmp_path / "agent-eval.yaml"
    dataset_path.write_text(
        """cases:
  - id: chicken-wash
    request:
      question: 生鸡肉要不要洗？
      mode: hybrid
    expect:
      should_retrieve: true
      required_step_kinds: [search, synthesize]
      expected_tools: [search_notes]
      expected_chunk_ids: [KB-072]
      expected_answer_points: [不建议清洗生鸡肉, 交叉污染]
""",
        encoding="utf-8",
    )

    dataset = load_agent_eval_dataset(dataset_path)

    assert len(dataset.cases) == 1
    case = dataset.cases[0]
    assert case.request.question == "生鸡肉要不要洗？"
    assert case.expect.expected_chunk_ids == ["KB-072"]
