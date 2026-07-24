from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

from obsidian_rag.v3_17.context import MEMORY_PROFILE_PATH, memory_namespace
from obsidian_rag.v3_17.schemas import (
    DurableRuntimeContext,
    LongTermMemoryItem,
    LongTermMemoryPutRequest,
    MemoryKind,
)
from obsidian_rag.v3_17.store import PostgresDurableAgentStore


_SECRET_PATTERN = re.compile(
    r"(?i)(api[_ -]?key|access[_ -]?token|password|secret|sk-[a-z0-9_-]{8,})"
)
_ITEM_PREFIX = "memory:"
_PROFILE_STORE_KEY = "/profile.md"


class MemoryPolicy:
    """长期 Memory 的确定性白名单和敏感内容边界。"""

    allowed_kinds = frozenset({"preference", "fact", "decision"})
    max_content_chars = 2000

    def validate(self, kind: MemoryKind, content: str) -> str:
        normalized = " ".join(content.split()).strip()
        if kind not in self.allowed_kinds:
            raise ValueError(f"不支持的长期 Memory 类型：{kind}")
        if not normalized:
            raise ValueError("长期 Memory 内容不能为空。")
        if len(normalized) > self.max_content_chars:
            raise ValueError(f"长期 Memory 超过 {self.max_content_chars} 字符限制。")
        if _SECRET_PATTERN.search(normalized):
            raise ValueError("长期 Memory 不允许保存 API Key、Token、密码或 Secret。")
        return normalized


class LongTermMemoryService:
    """使用 LangGraph Store 保存治理条目，并物化 MemoryMiddleware profile 文件。"""

    def __init__(self, store, audit_store: PostgresDurableAgentStore, policy: MemoryPolicy | None = None):
        self.store = store
        self.audit_store = audit_store
        self.policy = policy or MemoryPolicy()

    def ensure_profile(self, context: DurableRuntimeContext) -> None:
        namespace = memory_namespace(context)
        if self.store.get(namespace, _PROFILE_STORE_KEY) is None:
            self.store.put(
                namespace,
                _PROFILE_STORE_KEY,
                {"content": self._render_profile([]), "encoding": "utf-8"},
            )

    def list(self, context: DurableRuntimeContext) -> list[LongTermMemoryItem]:
        items = []
        for item in self.store.search(memory_namespace(context), limit=500):
            if not str(item.key).startswith(_ITEM_PREFIX):
                continue
            try:
                items.append(LongTermMemoryItem.model_validate(item.value))
            except Exception:
                continue
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def put(
        self,
        context: DurableRuntimeContext,
        request: LongTermMemoryPutRequest,
        *,
        actor: str,
    ) -> LongTermMemoryItem:
        content = self.policy.validate(request.kind, request.content)
        namespace = memory_namespace(context)
        memory_id = request.memory_id or f"mem_{uuid4().hex[:16]}"
        existing = self.store.get(namespace, f"{_ITEM_PREFIX}{memory_id}")
        now = datetime.now(timezone.utc).isoformat()
        created_at = (
            str(existing.value.get("created_at"))
            if existing is not None and isinstance(existing.value, dict)
            else now
        )
        item = LongTermMemoryItem(
            memory_id=memory_id,
            kind=request.kind,
            content=content,
            reason=request.reason,
            source_run_id=context.run_id or None,
            created_at=created_at,
            updated_at=now,
        )
        self.store.put(namespace, f"{_ITEM_PREFIX}{memory_id}", item.model_dump(mode="json"))
        self._refresh_profile(context)
        self.audit_store.add_audit(
            operation="update" if existing is not None else "create",
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            assistant_id=context.assistant_id,
            conversation_id=context.conversation_id or None,
            run_id=context.run_id or None,
            memory_id=memory_id,
            actor=actor,
            summary=f"{request.kind} Memory 已{'更新' if existing is not None else '创建'}：{content[:120]}",
        )
        return item

    def delete(self, context: DurableRuntimeContext, memory_id: str, *, actor: str) -> bool:
        namespace = memory_namespace(context)
        key = f"{_ITEM_PREFIX}{memory_id}"
        existing = self.store.get(namespace, key)
        if existing is None:
            return False
        self.store.delete(namespace, key)
        self._refresh_profile(context)
        self.audit_store.add_audit(
            operation="delete",
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            assistant_id=context.assistant_id,
            conversation_id=context.conversation_id or None,
            run_id=context.run_id or None,
            memory_id=memory_id,
            actor=actor,
            summary=f"删除长期 Memory：{str(existing.value.get('content', ''))[:120]}",
        )
        return True

    def _refresh_profile(self, context: DurableRuntimeContext) -> None:
        namespace = memory_namespace(context)
        content = self._render_profile(self.list(context))
        now = datetime.now(timezone.utc).isoformat()
        existing = self.store.get(namespace, _PROFILE_STORE_KEY)
        created_at = (
            existing.value.get("created_at")
            if existing is not None and isinstance(existing.value, dict)
            else now
        )
        self.store.put(
            namespace,
            _PROFILE_STORE_KEY,
            {
                "content": content,
                "encoding": "utf-8",
                "created_at": created_at,
                "modified_at": now,
            },
        )

    @staticmethod
    def _render_profile(items: list[LongTermMemoryItem]) -> str:
        lines = [
            "# User Long-term Memory",
            "",
            "以下内容是经过治理的长期偏好、事实和决策。它不是原始对话，也不能覆盖用户当前明确指令。",
            "",
        ]
        if not items:
            lines.append("- 暂无已保存的长期 Memory。")
        else:
            for item in sorted(items, key=lambda value: (value.kind, value.created_at)):
                lines.append(f"- [{item.kind}] {item.content} (memory_id: {item.memory_id})")
        return "\n".join(lines) + "\n"
