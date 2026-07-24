from obsidian_rag.v3_12_4.agent import RoutedMcpAgentService


class PermissionAwareAgentService(RoutedMcpAgentService):
    """在 V3.12.4 完整 Agent 上注入 Core Permission Policy。"""
