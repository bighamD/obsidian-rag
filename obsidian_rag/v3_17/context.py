from __future__ import annotations

from obsidian_rag.v3_17.schemas import DurableRuntimeContext


MEMORY_PROFILE_PATH = "/memories/profile.md"
CONTEXT_ARTIFACTS_ROOT = "/context"
SUMMARY_TRIGGER_FRACTION = 0.85


def memory_namespace(context: DurableRuntimeContext) -> tuple[str, ...]:
    """跨 Conversation 的用户长期 Memory namespace。"""

    return ("v3_17", "memory", context.tenant_id, context.assistant_id, context.user_id)


def thread_context_namespace(context: DurableRuntimeContext) -> tuple[str, ...]:
    """仅当前 Thread 可见的 Summary/Offloading namespace。"""

    return (
        "v3_17",
        "context",
        context.tenant_id,
        context.assistant_id,
        context.user_id,
        context.thread_id,
    )


def runtime_memory_namespace(runtime) -> tuple[str, ...]:
    return memory_namespace(DurableRuntimeContext.model_validate(runtime.context))


def runtime_thread_context_namespace(runtime) -> tuple[str, ...]:
    return thread_context_namespace(DurableRuntimeContext.model_validate(runtime.context))

