from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError


RouterAction = Literal["search", "no_search", "clarify"]


class RouterDecision(BaseModel):
    action: RouterAction
    intent: str = Field(min_length=1)
    search_query: str | None = None
    reason: str
    clarifying_question: str | None = None
    direct_answer: str | None = None


ROUTER_SYSTEM_PROMPT = """你是 Obsidian 本地知识库 RAG 的意图路由器。

你的任务是先判断用户问题是否应该查询本地知识库，再输出结构化 JSON。
只输出 JSON，不要输出 Markdown，不要解释。

可选 action：
- search：问题适合查询本地知识库，例如笔记、食品安全资料、项目文档、已入库资料。
- no_search：问题明显依赖实时外部信息、通用闲聊，或本地知识库无法可靠回答。
- clarify：问题太短、指代不明、范围不清，需要用户补充。

intent 建议使用：
- kb_question：适合查本地知识库的问题
- external_realtime：需要实时外部信息的问题，例如天气、股价、新闻
- chitchat：寒暄或闲聊
- ambiguous：问题模糊，需要追问

JSON 格式：
{
  "action": "search | no_search | clarify",
  "intent": "kb_question | external_realtime | chitchat | ambiguous",
  "search_query": "当 action=search 时给出适合检索的查询词，否则为 null",
  "reason": "一句话说明决策原因",
  "clarifying_question": "当 action=clarify 时给出追问，否则为 null",
  "direct_answer": "当 action=no_search 时可给出直接回复，否则为 null"
}
"""


class RouterService:
    def __init__(self, chat_client=None, chat_client_factory=None):
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory

    def route(self, question: str) -> RouterDecision:
        client = self._chat_client()
        if client is None:
            return RouterDecision(
                action="clarify",
                intent="router_unavailable",
                reason="没有配置 LLM Router 客户端，无法判断是否应该检索。",
                clarifying_question="我暂时无法判断你的问题是否需要查本地知识库，可以换一种更明确的问法吗？",
            )
        messages = [
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        return parse_router_json(client.complete(messages))

    def _chat_client(self):
        if self.chat_client is None and self.chat_client_factory is not None:
            self.chat_client = self.chat_client_factory()
        return self.chat_client


def parse_router_json(raw_output: str) -> RouterDecision:
    try:
        payload = json.loads(_extract_json(raw_output))
        return RouterDecision(**payload)
    except (json.JSONDecodeError, TypeError, ValidationError):
        return RouterDecision(
            action="clarify",
            intent="invalid_router_output",
            reason="LLM Router 没有返回可解析的结构化 JSON。",
            clarifying_question="我没有理解你的问题范围，可以补充一下你想查本地知识库里的哪类内容吗？",
        )


def _extract_json(raw_output: str) -> str:
    text = raw_output.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text

