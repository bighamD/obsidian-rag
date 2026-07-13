from obsidian_rag.cli import run_agent39_eval
from tests.v3_9.helpers import FakeAgentService


def test_run_agent39_eval_prints_batch_summary(tmp_path, capsys):
    dataset_path = tmp_path / "agent-eval.yaml"
    dataset_path.write_text(
        """cases:
  - id: chicken-wash
    request:
      question: 生鸡肉要不要洗？
    expect:
      should_retrieve: true
      expected_tools: [search_notes]
      expected_chunk_ids: [KB-072]
      expected_answer_points: [不建议清洗生鸡肉, 交叉污染]
""",
        encoding="utf-8",
    )

    run_agent39_eval(dataset_path=dataset_path, agent_service=FakeAgentService(), output_path=None)

    output = capsys.readouterr().out
    assert "Cases: 1" in output
    assert "Passed: 1" in output
    assert "Pass rate: 1.0000" in output
