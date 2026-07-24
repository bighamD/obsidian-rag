from obsidian_rag.v3_12_3.agent import McpAgentService


class RoutedMcpAgentService(McpAgentService):
    """组合 MCP Tool Selection 与 Core RetrievalScopeResolver 的完整 Agent。"""

