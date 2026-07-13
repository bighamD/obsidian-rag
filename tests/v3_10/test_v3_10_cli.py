from obsidian_rag.cli import run_agent310_ask
from obsidian_rag.v3_10.runtime.lifecycle import AgentRuntimeService
from obsidian_rag.v3_10.runtime.store import InMemoryRunStore
from tests.v3_9.helpers import FakeAgentService


def test_run_agent310_ask_prints_production_summary(capsys):
    runtime = AgentRuntimeService(agent_service=FakeAgentService(), run_store=InMemoryRunStore())

    run_agent310_ask(question="生鸡肉要不要洗？", config=None, runtime_service=runtime)

    output = capsys.readouterr().out
    assert "Production run: prod_" in output
    assert "Status: succeeded" in output
    assert "Tool: search_notes | calls=1 | success=1 | failed=0 | results=1" in output
    assert "不建议清洗生鸡肉，因为水花可能造成交叉污染。" in output
