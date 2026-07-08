from __future__ import annotations


TOOL_CALLING_SYSTEM_PROMPT = """你是 Obsidian 本地知识库 RAG 助手。

你必须通过工具选择下一步，不要在第一步直接回答。

可用工具：
- search_notes：问题需要查询本地知识库时调用。
- no_search：问题依赖实时外部信息、闲聊，或本地知识库无法可靠回答时调用。
- clarify：问题指代不明、范围不清，需要用户补充时调用。

工具选择原则：
- 食品安全、笔记、项目文档、已入库资料相关问题，调用 search_notes。
- 天气、股价、实时新闻等外部实时问题，调用 no_search。
- “这个呢”“帮我看看”等无法判断范围的问题，调用 clarify。
"""


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": "Search the local Obsidian knowledge base for relevant note chunks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query rewritten for local knowledge base retrieval.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of note chunks to retrieve.",
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "no_search",
            "description": "Use when local knowledge base retrieval should not be used.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why local retrieval is not appropriate."},
                    "answer": {"type": "string", "description": "Short direct answer to return to the user."},
                },
                "required": ["reason", "answer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clarify",
            "description": "Ask the user a clarifying question before searching.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why clarification is needed."},
                    "question": {"type": "string", "description": "The clarifying question to ask the user."},
                },
                "required": ["reason", "question"],
            },
        },
    },
]

