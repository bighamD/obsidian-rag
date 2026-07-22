from obsidian_rag.cli import run_agent314_sandbox


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"executed": True, "status": "success"}


def test_cli_calls_sandbox_tool(monkeypatch, capsys):
    monkeypatch.setattr("obsidian_rag.cli.httpx.post", lambda *args, **kwargs: FakeResponse())

    run_agent314_sandbox(
        api_base="http://127.0.0.1:8023",
        tool_name="list_files",
        run_id="run_cli",
        arguments_json="{}",
        principal_profile="sandbox",
    )

    assert '"executed": true' in capsys.readouterr().out
