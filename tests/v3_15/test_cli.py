from obsidian_rag.cli import run_agent315_resume


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"run": {"status": "succeeded"}, "approval": {"status": "resolved"}}


def test_cli_resumes_waiting_run(monkeypatch, capsys):
    monkeypatch.setattr("obsidian_rag.cli.httpx.post", lambda *args, **kwargs: FakeResponse())

    run_agent315_resume(
        run_id="hitl_test",
        action="allow",
        step_arguments_json="{}",
        comment="测试允许",
        api_base="http://127.0.0.1:8024",
    )

    assert '"status": "resolved"' in capsys.readouterr().out
