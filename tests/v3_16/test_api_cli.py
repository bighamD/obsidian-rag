import json

from fastapi.testclient import TestClient

from obsidian_rag import cli
from obsidian_rag.v3_16.app import app


def test_console_contract_declares_deepagents_without_conversation_memory():
    response = TestClient(app).get("/console/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend_version"] == "v3.16"
    assert payload["features"]["deep_agents"] is True
    assert payload["features"]["conversation_memory"] is False


def test_cli_inspect_reads_persisted_run(monkeypatch, capsys):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"run": {"run_id": "deep_123", "status": "succeeded"}}

    monkeypatch.setattr(cli.httpx, "get", lambda *args, **kwargs: Response())

    cli.run_agent316_inspect(run_id="deep_123", api_base="http://127.0.0.1:8025")

    assert json.loads(capsys.readouterr().out)["run"]["run_id"] == "deep_123"
