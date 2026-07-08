from obsidian_rag.v3_1.router.service import RouterDecision, RouterService, parse_router_json


class FakeRouterChatClient:
    def __init__(self, response: str):
        self.response = response
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return self.response


def test_parse_router_json_accepts_fenced_json():
    decision = parse_router_json(
        """
```json
{
  "action": "search",
  "intent": "kb_question",
  "search_query": "生鸡肉 清洗 交叉污染",
  "reason": "问题属于食品安全知识库范围。"
}
```
""".strip()
    )

    assert decision == RouterDecision(
        action="search",
        intent="kb_question",
        search_query="生鸡肉 清洗 交叉污染",
        reason="问题属于食品安全知识库范围。",
        clarifying_question=None,
        direct_answer=None,
    )


def test_router_service_returns_no_search_for_external_realtime_question():
    chat = FakeRouterChatClient(
        """
{
  "action": "no_search",
  "intent": "external_realtime",
  "search_query": null,
  "reason": "问题需要实时天气信息，本地知识库无法可靠回答。",
  "direct_answer": "这个问题需要查询实时天气服务。"
}
""".strip()
    )
    router = RouterService(chat_client=chat)

    decision = router.route("今天深圳天气怎么样")

    assert decision.action == "no_search"
    assert decision.intent == "external_realtime"
    assert decision.search_query is None
    assert decision.direct_answer == "这个问题需要查询实时天气服务。"
    assert "只输出 JSON" in chat.messages[0][0]["content"]


def test_parse_router_json_falls_back_to_clarify_on_invalid_json():
    decision = parse_router_json("我觉得应该查一下")

    assert decision.action == "clarify"
    assert decision.intent == "invalid_router_output"
    assert decision.clarifying_question == "我没有理解你的问题范围，可以补充一下你想查本地知识库里的哪类内容吗？"
