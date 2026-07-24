from obsidian_rag.v3_17.app import app


def test_v317_openapi_exposes_memory_and_conversation_routes():
    schema = app.openapi()
    assert schema["info"]["version"] == "v3.17"
    assert "/agent/ask" in schema["paths"]
    assert "/conversations" in schema["paths"]
    assert "/memories" in schema["paths"]
    assert "/memory-audits" in schema["paths"]
    assert "/recoveries/{run_id}/retry" in schema["paths"]
    assert "/recoveries/{run_id}/retry/stream" in schema["paths"]
