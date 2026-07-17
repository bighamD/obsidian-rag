from obsidian_rag.cli import run_agent3124_collections


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"enabled_ids": ["food_safety"]}


def test_cli_reads_collection_runtime(monkeypatch, capsys):
    monkeypatch.setattr("obsidian_rag.cli.httpx.get", lambda *args, **kwargs: FakeResponse())

    run_agent3124_collections(command="collections", api_base="http://127.0.0.1:8021")

    assert "food_safety" in capsys.readouterr().out
