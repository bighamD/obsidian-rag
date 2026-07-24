from obsidian_rag.v3_12_3.config import load_mcp_server_registry
from obsidian_rag.v3_12_3.connection import McpConnectionManager


def test_connection_manager_reuses_stdio_session():
    registry, path = load_mcp_server_registry()
    manager = McpConnectionManager(registry, path)
    manager.start()
    try:
        first = manager.call_tool("demo::get_server_time", {"timezone": "Asia/Shanghai"})
        second = manager.call_tool("demo::lookup_food_temperature", {"food": "chicken"})
        runtime = manager.runtime()
    finally:
        manager.stop()

    assert first.status == "success"
    assert second.trace[0].phase == "session_reused"
    assert runtime.servers[0].call_count == 2
