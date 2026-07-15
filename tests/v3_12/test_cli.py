from obsidian_rag import cli
from obsidian_rag.v3_12.schemas import McpToolListResponse


class FakeService:
    async def list_tools(self, server_name=None):
        return McpToolListResponse(
            requested_server=server_name,
            tools=[],
            errors={},
            duration_ms=1,
            trace=[],
        )


def test_cli_tools_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_mcp_service", lambda: FakeService())

    cli.run_mcp312("tools", server_name="demo")

    assert '"requested_server": "demo"' in capsys.readouterr().out
