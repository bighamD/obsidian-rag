from __future__ import annotations

from fnmatch import fnmatch
from typing import Any, Protocol
from uuid import uuid4

from jsonschema import Draft202012Validator, SchemaError

from obsidian_rag.core.permissions.audit import InMemoryPermissionAuditStore
from obsidian_rag.core.permissions.schemas import (
    PermissionAuditRecord,
    PermissionDecision,
    PermissionPrincipal,
    PermissionReport,
)
from obsidian_rag.core.tools import ToolDefinition, ToolRegistry


class PermissionPolicy(Protocol):
    def authorize(
        self,
        *,
        plan: Any,
        principal: PermissionPrincipal,
        tool_registry: ToolRegistry,
        retrieval_scope: Any,
        run_id: str,
        conversation_id: str,
    ) -> PermissionReport: ...


class StaticPermissionPolicy:
    """在 Tool Executor 前统一执行 allow/confirm/deny 的静态策略。"""

    def __init__(self, audit_store: InMemoryPermissionAuditStore | None = None):
        self.audit_store = audit_store

    def authorize(
        self,
        *,
        plan: Any,
        principal: PermissionPrincipal,
        tool_registry: ToolRegistry,
        retrieval_scope: Any,
        run_id: str,
        conversation_id: str,
    ) -> PermissionReport:
        definitions = {item.name: item for item in tool_registry.list_tools()}
        decisions = [
            self._authorize_step(step, principal, definitions, retrieval_scope)
            for step in plan.steps
        ]
        allow_count = sum(item.decision == "allow" for item in decisions)
        confirm_count = sum(item.decision == "confirm" for item in decisions)
        deny_count = sum(item.decision == "deny" for item in decisions)
        report = PermissionReport(
            principal=principal,
            decisions=decisions,
            allow_count=allow_count,
            confirm_count=confirm_count,
            deny_count=deny_count,
            all_allowed=confirm_count == 0 and deny_count == 0,
            summary=f"允许 {allow_count} 步，需要确认 {confirm_count} 步，拒绝 {deny_count} 步。",
        )
        if self.audit_store is not None:
            from datetime import datetime, timezone

            self.audit_store.append(
                PermissionAuditRecord(
                    audit_id=f"audit_{uuid4().hex[:12]}",
                    run_id=run_id,
                    conversation_id=conversation_id,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    report=report,
                )
            )
        return report

    def _authorize_step(
        self,
        step: Any,
        principal: PermissionPrincipal,
        definitions: dict[str, ToolDefinition],
        retrieval_scope: Any,
    ) -> PermissionDecision:
        if step.kind == "search":
            collections = list(getattr(retrieval_scope, "selected_collections", []) or [])
            return self._decide(
                step=step,
                principal=principal,
                definition=definitions.get("search_notes"),
                tool_name="search_notes",
                collections=collections,
                arguments={},
            )
        if step.kind == "tool":
            tool_name = step.tool_name or ""
            return self._decide(
                step=step,
                principal=principal,
                definition=definitions.get(tool_name),
                tool_name=tool_name,
                collections=[],
                arguments=dict(step.arguments),
            )
        return PermissionDecision(
            step_id=step.id,
            kind=step.kind,
            tool_name=None,
            source="agent",
            risk_level="safe",
            decision="allow",
            reason="该步骤不调用外部 Tool，可由 Agent 内部继续执行。",
        )

    def _decide(
        self,
        *,
        step: Any,
        principal: PermissionPrincipal,
        definition: ToolDefinition | None,
        tool_name: str,
        collections: list[str],
        arguments: dict[str, Any],
    ) -> PermissionDecision:
        if definition is None:
            return PermissionDecision(
                step_id=step.id,
                kind=step.kind,
                tool_name=tool_name or None,
                source="unknown",
                risk_level="restricted",
                decision="deny",
                reason="Tool Registry 中不存在该工具，默认拒绝执行。",
                argument_names=sorted(arguments),
            )

        risk_level = definition.risk_level or _risk_from_definition(definition)
        required_permissions = [definition.required_permission] if definition.required_permission else []
        missing_permissions = [
            item for item in required_permissions
            if not _matches_any(item, principal.permissions) and "admin" not in principal.roles
        ]
        tool_denied = not _matches_any(tool_name, principal.tool_allowlist) and "admin" not in principal.roles
        denied_collections = [
            item for item in collections
            if not _matches_any(item, principal.allowed_collections) and "admin" not in principal.roles
        ]
        validation_errors = _validate_arguments(definition.input_schema, arguments) if step.kind == "tool" else []

        if tool_denied:
            decision = "deny"
            reason = "Tool 不在当前 Principal 的 allowlist 中。"
        elif missing_permissions:
            decision = "deny"
            reason = "当前 Principal 缺少工具要求的权限。"
        elif denied_collections:
            decision = "deny"
            reason = "检索范围包含当前 Principal 无权访问的 Collection。"
        elif validation_errors:
            decision = "deny"
            reason = "Tool arguments 未通过 JSON Schema 校验。"
        elif risk_level == "safe":
            decision = "allow"
            reason = "只读低风险工具满足 allowlist、permission、scope 和参数约束。"
        elif risk_level == "confirm":
            decision = "confirm"
            reason = "该工具可能产生外部副作用，需要人工确认；V3.13 不自动执行。"
        else:
            decision = "deny"
            reason = "restricted 工具在未进入 Sandbox 前禁止执行。"

        return PermissionDecision(
            step_id=step.id,
            kind=step.kind,
            tool_name=tool_name,
            source=definition.source,
            risk_level=risk_level,
            decision=decision,
            reason=reason,
            required_permissions=required_permissions,
            missing_permissions=missing_permissions,
            collections=collections,
            denied_collections=denied_collections,
            argument_names=sorted(arguments),
            validation_errors=validation_errors,
        )


def _risk_from_definition(definition: ToolDefinition) -> str:
    if definition.read_only is True:
        return "safe"
    if definition.read_only is False:
        return "confirm"
    return "restricted"


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(fnmatch(value, pattern) for pattern in patterns)


def _validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> list[str]:
    if not schema:
        return []
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
    except SchemaError as exc:
        return [f"Tool Schema 无效：{exc.message}"]
    errors = sorted(validator.iter_errors(arguments), key=lambda item: list(item.absolute_path))
    return [error.message[:240] for error in errors]
