import json

from obsidian_rag.cli import run_agent3103_ask, run_agent3103_history


class FakeResponse:
    def __init__(self, payload=None, lines=None):
        self.payload = payload or {}
        self.lines = lines or []

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload

    def iter_lines(self):
        return iter(self.lines)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_run_agent3103_json_prints_answer_and_graph_path(monkeypatch, capsys):
    payload = {
        "run_id": "adv_json",
        "thread_id": "thread_json",
        "answer": "JSON 答案",
        "graph_path": ["load_memory", "answer", "save_memory"],
    }
    monkeypatch.setattr("obsidian_rag.cli.httpx.post", lambda *args, **kwargs: FakeResponse(payload=payload))

    run_agent3103_ask(question="测试 JSON", stream=False)

    output = capsys.readouterr().out
    assert "Run: adv_json | Thread: thread_json" in output
    assert "JSON 答案" in output
    assert "load_memory -> answer -> save_memory" in output


def test_run_agent3103_sse_prints_answer_delta(monkeypatch, capsys):
    delta = {
        "detail": "答案增量。",
        "data": {"delta": "流式答案"},
    }
    succeeded = {
        "detail": "完成。",
        "data": {"response": {"thread_id": "thread_stream"}},
    }
    lines = [
        "event: answer_delta",
        f"data: {json.dumps(delta, ensure_ascii=False)}",
        "",
        "event: run_succeeded",
        f"data: {json.dumps(succeeded, ensure_ascii=False)}",
        "",
    ]
    monkeypatch.setattr(
        "obsidian_rag.cli.httpx.stream",
        lambda *args, **kwargs: FakeResponse(lines=lines),
    )

    run_agent3103_ask(question="测试 SSE", stream=True)

    output = capsys.readouterr().out
    assert "V3.10.3 LangGraph stream" in output
    assert "流式答案" in output
    assert "Thread: thread_stream" in output


def test_run_agent3103_history_prints_checkpoint_summary(monkeypatch, capsys):
    payload = {
        "thread_id": "thread_history",
        "entries": [
            {
                "checkpoint_id": "cp_1",
                "next_nodes": ["answer"],
                "graph_path": ["load_memory", "build_context"],
            }
        ],
    }
    monkeypatch.setattr("obsidian_rag.cli.httpx.get", lambda *args, **kwargs: FakeResponse(payload=payload))

    run_agent3103_history("thread_history", limit=1)

    output = capsys.readouterr().out
    assert "Thread: thread_history | checkpoints=1" in output
    assert "cp_1" in output
    assert "next=answer" in output
