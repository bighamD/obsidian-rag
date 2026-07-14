from __future__ import annotations

import json

from obsidian_rag.v3_8_1.mysql_memory import MySQLConversationMemoryStore
from obsidian_rag.v3_8_1.schemas import MemoryCompactionResult, MemoryTurn


SUMMARY_SYSTEM_PROMPT = """你是 Conversation Memory 压缩器。
请把已有摘要和新增旧对话合并成一份简洁、准确、可供后续 Planner 与 Answer 使用的会话摘要。
保留用户目标、明确事实、重要约束、已经确认的结论和未解决问题。
不要编造信息，不要输出 Markdown 标题，只返回摘要正文。"""


class ConversationCompactor:
    def __init__(
        self,
        memory_store: MySQLConversationMemoryStore,
        chat_client=None,
        chat_client_factory=None,
    ):
        self.memory_store = memory_store
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory

    def compact(
        self,
        conversation_id: str,
        keep_recent_turns: int,
        trigger_turns: int,
        trigger_tokens: int,
        force: bool = False,
    ) -> MemoryCompactionResult:
        candidate = self.memory_store.load_compaction_candidate(conversation_id, keep_recent_turns)
        turns = candidate.turns_to_summarize
        estimated_tokens = _estimate_summary_input_tokens(candidate.existing_summary, turns)
        should_compact = bool(turns) and (
            force or len(turns) >= trigger_turns or estimated_tokens >= trigger_tokens
        )
        if not turns:
            return MemoryCompactionResult(
                conversation_id=conversation_id,
                force=force,
                preserved_turn_count=candidate.preserved_turn_count,
                reason="没有位于最近窗口之前、且尚未摘要的旧 Turn。",
            )
        if not should_compact:
            return MemoryCompactionResult(
                conversation_id=conversation_id,
                force=force,
                candidate_turn_count=len(turns),
                preserved_turn_count=candidate.preserved_turn_count,
                estimated_input_tokens=estimated_tokens,
                summary_text=candidate.existing_summary,
                summary_through_turn_id=candidate.summary_through_turn_id,
                reason="未达到 Memory Compaction 的 Turn 或 token 阈值。",
            )
        chat_client = self.chat_client
        if chat_client is None and self.chat_client_factory is not None:
            try:
                chat_client = self.chat_client_factory()
            except Exception as exc:
                return MemoryCompactionResult(
                    conversation_id=conversation_id,
                    attempted=True,
                    force=force,
                    candidate_turn_count=len(turns),
                    preserved_turn_count=candidate.preserved_turn_count,
                    estimated_input_tokens=estimated_tokens,
                    summary_text=candidate.existing_summary,
                    summary_through_turn_id=candidate.summary_through_turn_id,
                    reason=f"摘要 LLM 初始化失败，已保留最近原始 Turns：{exc}",
                )
        if chat_client is None:
            return MemoryCompactionResult(
                conversation_id=conversation_id,
                attempted=True,
                force=force,
                candidate_turn_count=len(turns),
                preserved_turn_count=candidate.preserved_turn_count,
                estimated_input_tokens=estimated_tokens,
                summary_text=candidate.existing_summary,
                summary_through_turn_id=candidate.summary_through_turn_id,
                reason="没有配置摘要 LLM，已保留最近原始 Turns 并跳过压缩。",
            )

        messages = _build_summary_messages(candidate.existing_summary, turns)
        try:
            summary_text = chat_client.complete(messages).strip()
            if not summary_text:
                raise ValueError("摘要 LLM 返回空文本")
            summary_through_turn_id = turns[-1].turn_id
            self.memory_store.save_summary(
                conversation_id=conversation_id,
                summary_text=summary_text,
                summary_through_turn_id=summary_through_turn_id,
            )
        except Exception as exc:
            return MemoryCompactionResult(
                conversation_id=conversation_id,
                attempted=True,
                force=force,
                candidate_turn_count=len(turns),
                preserved_turn_count=candidate.preserved_turn_count,
                estimated_input_tokens=estimated_tokens,
                summary_text=candidate.existing_summary,
                summary_through_turn_id=candidate.summary_through_turn_id,
                reason=f"Memory Compaction 失败，已降级使用现有摘要和最近 Turns：{exc}",
            )

        return MemoryCompactionResult(
            conversation_id=conversation_id,
            attempted=True,
            compacted=True,
            force=force,
            candidate_turn_count=len(turns),
            summarized_turn_count=len(turns),
            preserved_turn_count=candidate.preserved_turn_count,
            estimated_input_tokens=estimated_tokens,
            summary_text=summary_text,
            summary_through_turn_id=summary_through_turn_id,
            reason="已把旧 Turns 合并进滚动会话摘要，并保留最近原始 Turns。",
        )


def _build_summary_messages(existing_summary: str, turns: list[MemoryTurn]) -> list[dict[str, str]]:
    payload = {
        "existing_summary": existing_summary or None,
        "new_turns": [
            {
                "user": turn.user_message,
                "assistant": turn.assistant_message,
                "sources": turn.sources,
            }
            for turn in turns
        ],
    }
    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def _estimate_summary_input_tokens(existing_summary: str, turns: list[MemoryTurn]) -> int:
    text = existing_summary + "\n" + "\n".join(
        f"用户：{turn.user_message}\n助手：{turn.assistant_message}" for turn in turns
    )
    cjk_count = sum(1 for character in text if "\u4e00" <= character <= "\u9fff")
    other_count = len(text) - cjk_count
    return max(1, cjk_count // 2 + other_count // 4)
