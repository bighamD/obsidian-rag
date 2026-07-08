from obsidian_rag.v2.evaluation.metrics import evaluate_retrieval_example, summarize_retrieval_metrics


def test_evaluate_retrieval_example_scores_hit_mrr_and_source_recall():
    result = evaluate_retrieval_example(
        expected_source_files=["food.md", "temperature.md"],
        retrieved_source_files=["other.md", "food.md", "food.md"],
    )

    assert result.hit is True
    assert result.first_relevant_rank == 2
    assert result.reciprocal_rank == 0.5
    assert result.source_recall == 0.5
    assert result.matched_expected_source_files == ["food.md"]
    assert result.missing_expected_source_files == ["temperature.md"]


def test_summarize_retrieval_metrics_averages_examples():
    first = evaluate_retrieval_example(["a.md"], ["a.md"])
    second = evaluate_retrieval_example(["b.md", "c.md"], ["x.md", "c.md"])
    third = evaluate_retrieval_example(["d.md"], ["x.md"])

    summary = summarize_retrieval_metrics([first, second, third])

    assert summary.example_count == 3
    assert summary.hit_rate_at_k == 2 / 3
    assert summary.mean_reciprocal_rank == (1 + 0.5 + 0) / 3
    assert summary.mean_source_recall == (1 + 0.5 + 0) / 3
