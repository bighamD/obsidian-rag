from pathlib import Path

from obsidian_rag.cli import run_agent381_ask, run_agent381_compact
from obsidian_rag.config import RagConfig
from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_8_1.memory import SQLiteConversationMemoryStore
from obsidian_rag.v3_8_1.schemas import (
    AgentAskResponse,
    ContextBundle,
    EvidenceCheckResult,
    MemorySnapshot,
    MemoryCompactionResult,
    MemoryTurn,
    MemoryWriteResult,
    StepResult,
)


class FakeAgentService:
    def ask(self, request):
        return AgentAskResponse(
            run_id="run_cli",
            conversation_id=request.conversation_id or "conv_cli",
            question=request.question,
            answer="最终答案",
            used_retrieval=True,
            sources=["food.md"],
            plan=Plan(goal="回答问题", steps=[PlanStep(id="s1", kind="search", query="厨房 清洁")]),
            step_results=[StepResult(step_id="s1", kind="search", status="success", result_count=1)],
            retry_step_results=[],
            evidence_check=EvidenceCheckResult(is_sufficient=True, reason="有证据。"),
            context_bundle=ContextBundle(
                messages=[{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
                token_budget=4000,
                context_summary="已构建上下文。",
            ),
            memory_snapshot=MemorySnapshot(
                conversation_id="conv_cli",
                window=3,
                recent_turns=[
                    MemoryTurn(
                        turn_id="turn_1",
                        conversation_id="conv_cli",
                        user_message="生鸡肉要不要洗？",
                        assistant_message="不建议清洗。",
                        created_at="2026-07-10T10:00:00+00:00",
                    )
                ],
                total_turn_count=1,
                loaded_turn_count=1,
            ),
            memory_write=MemoryWriteResult(conversation_id="conv_cli", turn_id="turn_2", saved=True),
            memory_compaction=MemoryCompactionResult(
                conversation_id="conv_cli",
                reason="未达到压缩阈值。",
            ),
            graph_path=["load_memory", "compact_memory", "planner", "build_context", "synthesize_answer", "save_memory"],
            trace=[],
        )


def _config(tmp_path: Path) -> RagConfig:
    return RagConfig(
        api_key="test-key",
        base_url="http://127.0.0.1:8317/v1",
        chat_model="gpt-5.4-mini",
        embedding_model="qwen3-embedding:0.6b",
        embedding_dimensions=1024,
        embedding_provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        qdrant_url=None,
        db_path=tmp_path / "qdrant",
        collection_name="obsidian_notes",
        chunk_size=1200,
        chunk_overlap=150,
        min_score=0.35,
        vault_path=None,
    )


def test_run_agent381_ask_prints_memory_state(tmp_path: Path, capsys):
    run_agent381_ask(
        question="那厨房怎么清洁？",
        conversation_id="conv_cli",
        memory_window=3,
        config=_config(tmp_path),
        agent_service=FakeAgentService(),
    )

    output = capsys.readouterr().out
    assert "Conversation: conv_cli" in output
    assert "Memory: loaded=1 | total=1 | omitted=0" in output
    assert "生鸡肉要不要洗？ -> 不建议清洗。" in output
    assert "Memory write: saved=True | turn=turn_2" in output
    assert "Compaction: compacted=False" in output


class FakeSummaryClient:
    def complete(self, messages):
        return "此前讨论了食品安全。"


def test_run_agent381_compact_prints_summary(tmp_path: Path, capsys):
    memory_store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    memory_store.append_turn("conv_cli", "问题 1", "回答 1", [], [])
    memory_store.append_turn("conv_cli", "问题 2", "回答 2", [], [])

    run_agent381_compact(
        conversation_id="conv_cli",
        keep_recent_turns=1,
        trigger_turns=99,
        trigger_tokens=50000,
        force=True,
        config=_config(tmp_path),
        memory_store=memory_store,
        chat_client=FakeSummaryClient(),
    )

    output = capsys.readouterr().out
    assert "Compaction: compacted=True" in output
    assert "Summary: 此前讨论了食品安全。" in output
    assert "Recent turns: 1 | total turns: 2" in output
