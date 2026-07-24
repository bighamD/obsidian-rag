from obsidian_rag.cli import run_agent313_permission


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"report": {"summary": "需要确认"}}


def test_cli_evaluates_permission(monkeypatch, capsys):
    monkeypatch.setattr("obsidian_rag.cli.httpx.post", lambda *args, **kwargs: FakeResponse())

    run_agent313_permission(
        command="policy",
        api_base="http://127.0.0.1:8022",
        tool_name="local::simulate_workspace_write",
        arguments_json='{"path":"demo.md","content":"hello"}',
        principal_profile="writer",
    )

    assert "需要确认" in capsys.readouterr().out
