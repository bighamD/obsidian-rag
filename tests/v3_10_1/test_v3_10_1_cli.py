from obsidian_rag.cli import run_agent3101_ask
from obsidian_rag.v3_10.runtime.lifecycle import AgentRuntimeService
from obsidian_rag.v3_10.runtime.store import InMemoryRunStore
from tests.v3_9.helpers import FakeAgentService


def test_run_agent3101_ask_prints_console_json_header(capsys):
    runtime = AgentRuntimeService(agent_service=FakeAgentService(), run_store=InMemoryRunStore())

    run_agent3101_ask(question="生鸡肉要不要洗？", config=None, runtime_service=runtime)

    output = capsys.readouterr().out
    assert "Agent Console JSON flow" in output
    assert "Status: succeeded" in output
