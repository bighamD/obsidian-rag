from pathlib import Path


def test_cli_contains_v317_entrypoint():
    source = Path("obsidian_rag/cli.py").read_text(encoding="utf-8")
    assert '"agent-v3-17"' in source
    assert "run_agent317_ask" in source
    assert "run_agent317_memory" in source
    assert 'agent317_subparsers.add_parser(\n        "recover"' in source
    assert "run_agent315_recover" in source
