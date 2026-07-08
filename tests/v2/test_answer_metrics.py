from obsidian_rag.v2.evaluation.answer import evaluate_answer_example


def test_evaluate_answer_example_scores_source_and_answer_point_coverage():
    metrics = evaluate_answer_example(
        answer="不建议冲洗生鸡肉，因为水花会造成交叉污染。鸡肉要充分加热。",
        expected_source_files=["food.md", "temperature.md"],
        cited_source_files=["food.md"],
        expected_answer_points=["不建议冲洗生鸡肉", "充分加热", "冷藏保存"],
    )

    assert metrics.source_coverage == 0.5
    assert metrics.answer_point_coverage == 2 / 3
    assert metrics.citation_present is True
    assert metrics.matched_answer_points == ["不建议冲洗生鸡肉", "充分加热"]
    assert metrics.missing_answer_points == ["冷藏保存"]
