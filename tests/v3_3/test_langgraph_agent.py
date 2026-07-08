from obsidian_rag.llm import ToolCall, ToolCallingResponse
from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_3.agent.service import AgentService
from obsidian_rag.v3_3.schemas import AgentAskRequest


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
    def __init__(self, results=None):
        self.calls = []
        self.results = results

    def search(self, query, top_k=5, mode="hybrid", filters=None):
        self.calls.append({"query": query, "top_k": top_k, "mode": mode, "filters": filters})
        if self.results is not None:
            return self.results
        return [
            SearchResult(
                chunk=TextChunk(
                    text="不建议清洗生鸡肉，因为水花可能造成交叉污染。",
                    metadata={"source": "food.md", "chunk_id": "KB-072", "topic": "不建议清洗生鸡肉"},
                ),
                score=0.91,
            )
        ]


def test_langgraph_runs_search_notes_path_and_records_graph_nodes():
    chat = FakeToolChatClient(
        ToolCallingResponse(
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="search_notes",
                    arguments={"query": "生鸡肉 清洗 交叉污染", "top_k": 3},
                )
            ]
        ),
        final_answer="基于资料：不建议清洗生鸡肉。",
    )
    retrieval = FakeRetrievalService()
    service = AgentService(retrieval_service=retrieval, chat_client=chat)

    response = service.ask(AgentAskRequest(question="生鸡肉还需要清洗下锅吗", top_k=5, mode="hybrid"))

    assert response.used_retrieval is True
    assert response.answer == "基于资料：不建议清洗生鸡肉。"
    assert response.graph_path == ["select_tool", "search_notes", "evidence_check", "answer"]
    assert [step.node_name for step in response.trace] == response.graph_path
    assert response.trace[0].tool_name == "search_notes"
    assert response.trace[1].result_count == 1
    assert retrieval.calls == [{"query": "生鸡肉 清洗 交叉污染", "top_k": 3, "mode": "hybrid", "filters": None}]
    assert chat.final_messages[0][-1]["role"] == "tool"


def test_langgraph_routes_no_search_to_terminal_answer_without_retrieval():
    chat = FakeToolChatClient(
        ToolCallingResponse(
            tool_calls=[
                ToolCall(
                    id="call_2",
                    name="no_search",
                    arguments={"reason": "需要实时天气。", "answer": "请查看实时天气服务。"},
                )
            ]
        )
    )
    retrieval = FakeRetrievalService()
    service = AgentService(retrieval_service=retrieval, chat_client=chat)

    response = service.ask(AgentAskRequest(question="今天深圳天气怎么样"))

    assert response.used_retrieval is False
    assert response.answer == "请查看实时天气服务。"
    assert response.graph_path == ["select_tool", "no_search"]
    assert retrieval.calls == []


def test_langgraph_routes_clarify_without_retrieval():
    chat = FakeToolChatClient(
        ToolCallingResponse(
            tool_calls=[
                ToolCall(
                    id="call_3",
                    name="clarify",
                    arguments={"reason": "问题指代不明。", "question": "你想查哪类本地知识？"},
                )
            ]
        )
    )
    service = AgentService(retrieval_service=FakeRetrievalService(), chat_client=chat)

    response = service.ask(AgentAskRequest(question="这个呢"))

    assert response.used_retrieval is False
    assert response.answer == "你想查哪类本地知识？"
    assert response.graph_path == ["select_tool", "clarify"]

