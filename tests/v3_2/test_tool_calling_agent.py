from obsidian_rag.llm import ToolCall, ToolCallingResponse
from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_2.agent.service import AgentService
from obsidian_rag.v3_2.schemas import AgentAskRequest


class FakeToolChatClient:
    def __init__(self, first_response: ToolCallingResponse, final_answer: str = "最终答案"):
        self.first_response = first_response
        self.final_answer = final_answer
        self.tool_requests = []
        self.final_messages = []

    def complete_with_tools(self, messages, tools):
        self.tool_requests.append({"messages": messages, "tools": tools})
        return self.first_response

    def complete(self, messages):
        self.final_messages.append(messages)
        return self.final_answer


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
                score=0.91,
            )
        ]


def test_agent_executes_search_notes_tool_call_and_sends_tool_result_back_to_llm():
    tool_client = FakeToolChatClient(
        ToolCallingResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="search_notes",
                    arguments={"query": "生鸡肉 清洗 交叉污染", "top_k": 3},
                )
            ],
        ),
        final_answer="基于资料：不建议清洗生鸡肉。",
    )
    retrieval = FakeRetrievalService()
    service = AgentService(retrieval_service=retrieval, chat_client=tool_client)

    response = service.ask(AgentAskRequest(question="生鸡肉还需要清洗下锅吗", top_k=5, mode="hybrid"))

    assert retrieval.calls == [{"query": "生鸡肉 清洗 交叉污染", "top_k": 3, "mode": "hybrid", "filters": None}]
    assert response.used_retrieval is True
    assert response.answer == "基于资料：不建议清洗生鸡肉。"
    assert response.tool_calls[0].name == "search_notes"
    assert response.trace[0].step_type == "tool_selection"
    assert response.trace[0].tool_name == "search_notes"
    assert response.trace[1].step_type == "tool_result"
    assert response.trace[1].result_count == 1
    assert tool_client.tool_requests[0]["tools"][0]["function"]["name"] == "search_notes"
    assert tool_client.final_messages[0][-1]["role"] == "tool"
    assert response.sources == ["food.md"]


def test_agent_falls_back_to_evidence_summary_when_final_llm_answer_is_empty():
    tool_client = FakeToolChatClient(
        ToolCallingResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="search_notes",
                    arguments={"query": "生鸡肉 清洗 交叉污染", "top_k": 3},
                )
            ],
        ),
        final_answer="",
    )
    service = AgentService(retrieval_service=FakeRetrievalService(), chat_client=tool_client)

    response = service.ask(AgentAskRequest(question="生鸡肉还需要清洗下锅吗", top_k=5, mode="hybrid"))

    assert response.used_retrieval is True
    assert "已找到本地资料" in response.answer
    assert "不建议清洗生鸡肉" in response.answer


def test_agent_returns_no_search_tool_result_without_retrieval():
    tool_client = FakeToolChatClient(
        ToolCallingResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_2",
                    name="no_search",
                    arguments={
                        "reason": "问题需要实时天气信息，本地知识库无法可靠回答。",
                        "answer": "这个问题需要查询实时天气服务。",
                    },
                )
            ],
        )
    )
    retrieval = FakeRetrievalService()
    service = AgentService(retrieval_service=retrieval, chat_client=tool_client)

    response = service.ask(AgentAskRequest(question="今天深圳天气怎么样"))

    assert response.used_retrieval is False
    assert response.answer == "这个问题需要查询实时天气服务。"
    assert retrieval.calls == []
    assert response.tool_calls[0].name == "no_search"
    assert [step.step_type for step in response.trace] == ["tool_selection", "answer"]


def test_agent_returns_clarify_tool_result_without_retrieval():
    tool_client = FakeToolChatClient(
        ToolCallingResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_3",
                    name="clarify",
                    arguments={
                        "reason": "问题指代不明。",
                        "question": "你想查哪类本地知识库内容？",
                    },
                )
            ],
        )
    )
    retrieval = FakeRetrievalService()
    service = AgentService(retrieval_service=retrieval, chat_client=tool_client)

    response = service.ask(AgentAskRequest(question="这个呢"))

    assert response.used_retrieval is False
    assert response.answer == "你想查哪类本地知识库内容？"
    assert retrieval.calls == []
    assert response.tool_calls[0].name == "clarify"
    assert [step.step_type for step in response.trace] == ["tool_selection", "answer"]
