from pathlib import Path


def test_resume_uses_command_and_stable_thread_config():
    source = Path("obsidian_rag/v3_17/agent.py").read_text(encoding="utf-8")
    assert "Command(resume=" in source
    assert '"thread_id": context.thread_id' in source
    assert "context=context" in source


def test_recover_continues_without_new_user_message():
    source = Path("obsidian_rag/v3_17/agent.py").read_text(encoding="utf-8")
    assert "def recover(" in source
    assert "if snapshot.interrupts:" in source
    assert "if not snapshot.next:" in source
    assert "self._stream_graph(graph, None" in source


def test_recover_routes_are_registered():
    app_source = Path("obsidian_rag/v3_17/app.py").read_text(encoding="utf-8")
    route_source = Path("obsidian_rag/v3_17/routes/recoveries.py").read_text(encoding="utf-8")
    assert "app.include_router(recoveries.router)" in app_source
    assert '@router.post("/{run_id}/retry"' in route_source
    assert '@router.post("/{run_id}/retry/stream"' in route_source
