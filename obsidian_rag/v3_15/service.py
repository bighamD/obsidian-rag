from __future__ import annotations

from obsidian_rag.v3_15.schemas import ApprovalDecisionInput, ApprovalListResponse, HitlRuntimeConfigResponse
from obsidian_rag.v3_14.service import SandboxLearningService


class HitlLearningService(SandboxLearningService):
    """聚合 V3.15 Runtime、Store 与沿用的 V3.14 能力查询。"""

    def __init__(self, *, store, agent_factory, postgres_settings, **kwargs):
        # 在 V3.14 服务基础上追加 HITL 依赖：持久 store、Agent 工厂、PG 配置。
        super().__init__(**kwargs)
        self.store = store
        self.agent_factory = agent_factory
        self.postgres_settings = postgres_settings

    def ask(self, request):
        """同步首次执行，委托给 Runtime。"""

        return self.runtime.ask(request)

    def start_stream(self, request):
        """SSE 首次执行，返回 run_id 供订阅。"""

        return self.runtime.start_stream(request)

    def stream(self, run_id: str):
        """返回某 Run 的 SSE 事件迭代器。"""

        return self.runtime.stream(run_id)

    def approval(self, run_id: str):
        """查询某 Run 的审批记录。"""

        return self.store.get_approval(run_id)

    def approvals(self, status: str | None, limit: int) -> ApprovalListResponse:
        """列出审批记录，供审批队列页面使用。"""

        return ApprovalListResponse(approvals=self.store.list_approvals(status=status, limit=limit))

    def resume(self, run_id: str, decision: ApprovalDecisionInput):
        """带人工决定同步恢复暂停的 Run。"""

        return self.runtime.resume(run_id, decision)

    def start_resume_stream(self, run_id: str, decision: ApprovalDecisionInput):
        """带人工决定以 SSE 方式恢复暂停的 Run。"""

        return self.runtime.start_resume_stream(run_id, decision)

    def recover(self, run_id: str):
        """同步恢复失败的 Run。"""

        return self.runtime.recover(run_id)

    def start_recovery_stream(self, run_id: str):
        """以 SSE 方式恢复失败的 Run。"""

        return self.runtime.start_recovery_stream(run_id)

    def runtime_config(self) -> HitlRuntimeConfigResponse:
        """汇总 V3.15 运行时能力与各端点，供 Swagger/前端观察。"""

        return HitlRuntimeConfigResponse(
            version="v3.15",
            checkpoint_backend="LangGraph PostgresSaver",
            runtime_store_backend="PostgreSQL JSONB",
            postgres_location=self.postgres_settings.display_location(),
            postgres_database=self.postgres_settings.database,
            postgres_schema=self.postgres_settings.schema,
            interrupt_enabled=True,
            resume_enabled=True,
            idempotency_enabled=True,
            json_endpoint="/agent/ask",
            stream_endpoint="/agent/ask/stream",
            approval_endpoint="/approvals/{run_id}",
            resume_endpoint="/approvals/{run_id}/resume",
            resume_stream_endpoint="/approvals/{run_id}/resume/stream",
            recovery_endpoint="/recoveries/{run_id}/retry",
            recovery_stream_endpoint="/recoveries/{run_id}/retry/stream",
        )
