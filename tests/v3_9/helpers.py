from obsidian_rag.v1.schemas import SearchHit
from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_8_1.schemas import (
    AgentAskResponse,
    ContextBundle,
    EvidenceCheckResult,
    MemoryCompactionResult,
    MemorySnapshot,
    MemoryWriteResult,
    StepResult,
)


class FakeAgentService:
    def __init__(self):
        self.requests = []

    def ask(self, request):
        self.requests.append(request)
        hit = SearchHit(
            chunk_id="KB-072",
            source="food.md",
            topic="生鸡肉清洗",
            score=0.9,
            text_preview="不建议清洗生鸡肉，以免交叉污染。",
            metadata={"chunk_id": "KB-072", "source": "food.md"},
        )
        return AgentAskResponse(
            run_id="run_eval",
            conversation_id=request.conversation_id or "conv_eval",
            question=request.question,
            answer="不建议清洗生鸡肉，因为水花可能造成交叉污染。",
            used_retrieval=True,
            sources=["food.md"],
            plan=Plan(
                goal="回答食品安全问题",
                steps=[
                    PlanStep(id="s1", kind="search", query="生鸡肉 清洗"),
                    PlanStep(id="s2", kind="synthesize", instruction="综合答案", depends_on=["s1"]),
                ],
            ),
            step_results=[
                StepResult(
                    step_id="s1",
                    kind="search",
                    tool_name="search_notes",
                    query="生鸡肉 清洗",
                    status="success",
                    result_count=1,
                    results=[hit],
                    sources=["food.md"],
                )
            ],
            retry_step_results=[],
            evidence_check=EvidenceCheckResult(is_sufficient=True, reason="检索到证据。"),
            context_bundle=ContextBundle(
                messages=[{"role": "system", "content": "system"}, {"role": "user", "content": "context"}],
                token_budget=4000,
                context_summary="已构建上下文。",
            ),
            memory_snapshot=MemorySnapshot(conversation_id=request.conversation_id or "conv_eval", window=3),
            memory_compaction=MemoryCompactionResult(
                conversation_id=request.conversation_id or "conv_eval",
                reason="未达到压缩阈值。",
            ),
            memory_write=MemoryWriteResult(
                conversation_id=request.conversation_id or "conv_eval",
                turn_id="turn_eval",
                saved=True,
            ),
            graph_path=["planner", "execute_steps", "save_memory"],
            trace=[],
        )
