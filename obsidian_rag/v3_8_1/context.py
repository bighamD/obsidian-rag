from __future__ import annotations

import json

from obsidian_rag.v1.schemas import SearchHit
from obsidian_rag.v3_4.schemas import Plan
from obsidian_rag.v3_8_1.schemas import ContextBundle, ContextChunk, EvidenceCheckResult, MemorySnapshot, StepResult


class ContextBuilder:
    def __init__(self, max_chunks: int = 6, token_budget: int = 4000):
        self.max_chunks = max_chunks
        self.token_budget = token_budget

    def build(
        self,
        question: str,
        plan: Plan,
        step_results: list[StepResult],
        retry_step_results: list[StepResult],
        evidence_check: EvidenceCheckResult,
        memory_snapshot: MemorySnapshot,
    ) -> ContextBundle:
        candidates = _collect_context_chunks([*step_results, *retry_step_results])
        ranked = sorted(candidates, key=_context_rank_key)
        included = ranked[: self.max_chunks]
        excluded = [
            chunk.model_copy(update={"reason": "超过 max_chunks 或优先级较低"}) for chunk in ranked[self.max_chunks :]
        ]
        messages = _build_messages(
            question=question,
            plan=plan,
            evidence_check=evidence_check,
            included_chunks=included,
            token_budget=self.token_budget,
            memory_snapshot=memory_snapshot,
        )
        return ContextBundle(
            messages=messages,
            included_chunks=included,
            excluded_chunks=excluded,
            token_budget=self.token_budget,
            context_summary=f"已选择 {len(included)} 个 chunks，排除 {len(excluded)} 个 chunks。",
        )


def _collect_context_chunks(step_results: list[StepResult]) -> list[ContextChunk]:
    chunks: list[ContextChunk] = []
    for step_result in step_results:
        for hit in step_result.results:
            chunks.append(_context_chunk_from_hit(step_result.step_id, hit))
    return chunks


def _context_chunk_from_hit(step_id: str, hit: SearchHit) -> ContextChunk:
    return ContextChunk(
        step_id=step_id,
        chunk_id=hit.chunk_id,
        source=hit.source,
        topic=hit.topic,
        score=hit.score,
        text_preview=hit.text_preview,
        reason="带 chunk_id，优先进入上下文" if hit.chunk_id else "没有 chunk_id，优先级低于已标注 chunk",
    )


def _context_rank_key(chunk: ContextChunk) -> tuple[int, float]:
    has_chunk_id_rank = 0 if chunk.chunk_id else 1
    return (has_chunk_id_rank, -chunk.score)


def _build_messages(
    question: str,
    plan: Plan,
    evidence_check: EvidenceCheckResult,
    included_chunks: list[ContextChunk],
    token_budget: int,
    memory_snapshot: MemorySnapshot,
) -> list[dict[str, str]]:
    context_payload = {
        "question": question,
        "plan": plan.model_dump(),
        "evidence_check": evidence_check.model_dump(),
        "token_budget": token_budget,
        "conversation_summary": memory_snapshot.summary_text or None,
        "conversation_memory": [turn.model_dump() for turn in memory_snapshot.recent_turns],
        "included_chunks": [chunk.model_dump() for chunk in included_chunks],
    }
    return [
        {
            "role": "system",
            "content": "你是 Obsidian 本地知识库 RAG 的答案综合器。只能基于 ContextBundle 中的证据回答，并在答案中保留来源线索。",
        },
        {"role": "user", "content": json.dumps(context_payload, ensure_ascii=False)},
    ]


def build_memory_aware_planner_question(question: str, memory_snapshot: MemorySnapshot) -> str:
    if not memory_snapshot.summary_text and not memory_snapshot.recent_turns:
        return question

    context_sections = []
    if memory_snapshot.summary_text:
        context_sections.append(f"会话摘要：\n{memory_snapshot.summary_text}")

    history_lines = []
    for turn in memory_snapshot.recent_turns:
        history_lines.append(f"用户：{turn.user_message}")
        history_lines.append(f"助手：{turn.assistant_message}")
    if history_lines:
        context_sections.append("最近对话历史：\n" + "\n".join(history_lines))
    memory_context = "\n\n".join(context_sections)
    return f"""当前问题：
{question}

{memory_context}

请结合会话摘要和最近对话理解当前问题中的指代，但只规划当前问题需要执行的步骤。"""
