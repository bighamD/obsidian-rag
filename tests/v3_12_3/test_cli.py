import json

from obsidian_rag import cli


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"started": True, "servers": [], "tools": [], "errors": {}}


def test_cli_reads_mcp_runtime(monkeypatch, capsys):
    monkeypatch.setattr(cli.httpx, "get", lambda *args, **kwargs: FakeResponse())

    cli.run_agent3123_mcp(command="mcp-status", api_base="http://127.0.0.1:8020")

    assert json.loads(capsys.readouterr().out)["started"] is True
