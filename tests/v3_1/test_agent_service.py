from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_1.agent.service import AgentService
from obsidian_rag.v3_1.router.service import RouterDecision
from obsidian_rag.v3_1.schemas import AgentAskRequest


class FakeRouter:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def route(self, question):
        self.calls.append(question)
        return self.decision


class FakeRetrievalService:
    def __init__(self):
        self.calls = []

    def search(self, query, top_k=5, mode="hybrid", filters=None):
        self.calls.append({"query": query, "top_k": top_k, "mode": mode, "filters": filters})
        return [
            SearchResult(
                chunk=TextChunk(
                    text="不建议清洗生鸡肉，因为水花可能造成交叉污染。",
                    metadata={"source": "food.md", "chunk_id": "KB-072", "topic": "不建议清洗生鸡肉"},
                ),
                score=0.93,
            )
        ]


class FakeChatClient:
    def __init__(self):
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return "基于资料：不建议清洗生鸡肉，因为水花可能造成交叉污染。"


def test_agent_uses_router_search_query_before_retrieval():
    router = FakeRouter(
        RouterDecision(
            action="search",
            intent="kb_question",
            search_query="生鸡肉 清洗 交叉污染",
            reason="问题属于食品安全知识库范围。",
        )
    )
    retrieval = FakeRetrievalService()
    chat = FakeChatClient()
    service = AgentService(router_service=router, retrieval_service=retrieval, chat_client=chat)

    response = service.ask(AgentAskRequest(question="生鸡肉还需要清洗下锅吗", top_k=3, mode="hybrid"))

    assert router.calls == ["生鸡肉还需要清洗下锅吗"]
    assert retrieval.calls == [{"query": "生鸡肉 清洗 交叉污染", "top_k": 3, "mode": "hybrid", "filters": None}]
    assert response.used_retrieval is True
    assert response.router.action == "search"
    assert [step.step_type for step in response.trace] == ["router", "search", "evidence", "answer"]
    assert response.trace[0].decision == "search"
    assert response.trace[1].query == "生鸡肉 清洗 交叉污染"
    assert response.sources == ["food.md"]


def test_agent_returns_direct_answer_without_retrieval_when_router_says_no_search():
    router = FakeRouter(
        RouterDecision(
            action="no_search",
            intent="external_realtime",
            reason="问题需要实时天气信息，本地知识库无法可靠回答。",
            direct_answer="这个问题需要查询实时天气服务，本地知识库不能保证准确。",
        )
    )
    retrieval = FakeRetrievalService()
    chat = FakeChatClient()
    service = AgentService(router_service=router, retrieval_service=retrieval, chat_client=chat)

    response = service.ask(AgentAskRequest(question="今天深圳天气怎么样"))

    assert response.used_retrieval is False
    assert response.answer == "这个问题需要查询实时天气服务，本地知识库不能保证准确。"
    assert retrieval.calls == []
    assert chat.messages == []
    assert response.router.intent == "external_realtime"
    assert [step.step_type for step in response.trace] == ["router", "answer"]


def test_agent_returns_clarifying_question_when_router_says_clarify():
    router = FakeRouter(
        RouterDecision(
            action="clarify",
            intent="ambiguous",
            reason="问题太短，无法判断要查什么。",
            clarifying_question="你想查食品安全、项目文档，还是别的知识库内容？",
        )
    )
    service = AgentService(router_service=router, retrieval_service=FakeRetrievalService(), chat_client=FakeChatClient())

    response = service.ask(AgentAskRequest(question="这个呢"))

    assert response.used_retrieval is False
    assert response.answer == "你想查食品安全、项目文档，还是别的知识库内容？"
    assert response.router.action == "clarify"
    assert [step.step_type for step in response.trace] == ["router", "answer"]
