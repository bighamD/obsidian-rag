from __future__ import annotations

import json

from obsidian_rag.v1.schemas import SearchHit
from obsidian_rag.core.schemas import ContextBundle, ContextChunk, EvidenceCheckResult, MemorySnapshot, Plan, StepResult


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
        dense_rank=hit.dense_rank,
        keyword_rank=hit.keyword_rank,
        dense_score=hit.dense_score,
        keyword_score=hit.keyword_score,
        hybrid_score=hit.hybrid_score,
        text_preview=hit.text_preview,
        text=hit.text,
        metadata=hit.metadata,
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
        "included_chunks": [_prompt_chunk(chunk) for chunk in included_chunks],
    }
    return [
        {
            "role": "system",
            "content": (
                "你是 Obsidian Agent 的答案生成器。请根据 ContextBundle 中的 question、plan、"
                "conversation_memory 和 included_chunks 完成当前请求。"
                "当 included_chunks 非空时，优先基于知识库证据回答，并保留 chunk_id 或来源线索；"
                "当 included_chunks 为空且计划是 no_search 时，直接回答不依赖本地知识库的通用问题，"
                "不要伪造知识库来源。对于天气、新闻、股价等需要实时外部数据的问题，明确说明当前没有对应外部工具，"
                "不要编造实时事实。对于 clarify 计划，向用户提出必要的澄清问题。"
            ),
        },
        {"role": "user", "content": json.dumps(context_payload, ensure_ascii=False)},
    ]


def _prompt_chunk(chunk: ContextChunk) -> dict[str, object]:
    """保留 Answer 节点原有的轻量证据字段，隔离 Console 调试扩展字段。"""

    return {
        "step_id": chunk.step_id,
        "chunk_id": chunk.chunk_id,
        "source": chunk.source,
        "topic": chunk.topic,
        "score": chunk.score,
        "text_preview": chunk.text_preview,
        "reason": chunk.reason,
    }


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
