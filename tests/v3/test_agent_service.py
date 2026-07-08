from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3.agent.service import AgentService
from obsidian_rag.v3.schemas import AgentAskRequest


class FakeRetrievalService:
    def __init__(self):
        self.calls = []

    def search(self, query, top_k=5, mode="hybrid", filters=None):
        self.calls.append({"query": query, "top_k": top_k, "mode": mode, "filters": filters})
        return [
            SearchResult(
                chunk=TextChunk(
                    text="不建议清洗生鸡肉，处理后要洗手并清洁水槽周边。",
                    metadata={"source": "food.md", "chunk_id": "KB-072", "topic": "不建议清洗生鸡肉"},
                ),
                score=0.91,
            )
        ]


class FakeChatClient:
    def __init__(self):
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return "基于资料：不建议清洗生鸡肉，处理后要洗手并清洁周边。"


def test_agent_answers_simple_chat_without_searching():
    retrieval = FakeRetrievalService()
    chat = FakeChatClient()
    service = AgentService(retrieval_service=retrieval, chat_client=chat)

    response = service.ask(AgentAskRequest(question="你好", top_k=3, mode="hybrid"))

    assert response.answer == "你好，我是本地知识库 RAG 助手。你可以问我需要查资料的问题。"
    assert response.used_retrieval is False
    assert retrieval.calls == []
    assert chat.messages == []
    assert response.trace[0].step_type == "decision"
    assert response.trace[0].decision == "no_search"


def test_agent_searches_notes_and_returns_trace_for_knowledge_question():
    retrieval = FakeRetrievalService()
    chat = FakeChatClient()
    service = AgentService(retrieval_service=retrieval, chat_client=chat)

    response = service.ask(AgentAskRequest(question="生鸡肉要清洗吗？", top_k=3, mode="hybrid"))

    assert response.used_retrieval is True
    assert response.answer.startswith("基于资料")
    assert retrieval.calls == [{"query": "生鸡肉要清洗吗？", "top_k": 3, "mode": "hybrid", "filters": None}]
    assert len(chat.messages) == 1
    assert [step.step_type for step in response.trace] == ["decision", "search", "evidence", "answer"]
    assert response.trace[1].tool_name == "search_notes"
    assert response.trace[1].query == "生鸡肉要清洗吗？"
    assert response.trace[1].result_count == 1
    assert response.sources == ["food.md"]


def test_agent_runs_second_search_for_multi_hop_question():
    retrieval = FakeRetrievalService()
    chat = FakeChatClient()
    service = AgentService(retrieval_service=retrieval, chat_client=chat)

    response = service.ask(AgentAskRequest(question="生鸡肉要不要洗，处理完后厨房怎么清洁？", top_k=2, mode="hybrid"))

    assert response.used_retrieval is True
    assert len(retrieval.calls) == 2
    assert retrieval.calls[0]["query"] == "生鸡肉要不要洗，处理完后厨房怎么清洁？"
    assert retrieval.calls[1]["query"] == "厨房 清洁 洗手 交叉污染"
    assert [step.step_type for step in response.trace].count("search") == 2
