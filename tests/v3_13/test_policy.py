from obsidian_rag.core.permissions import PermissionPrincipal, StaticPermissionPolicy
from obsidian_rag.core.schemas import Plan, PlanStep
from obsidian_rag.core.tools import ToolDefinition, ToolRegistry, ToolResult


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        "search_notes",
        lambda **_: ToolResult(tool_name="search_notes", status="success"),
        ToolDefinition(
            name="search_notes",
            read_only=True,
            risk_level="safe",
            required_permission="knowledge.read",
        ),
    )
    registry.register(
        "local::write",
        lambda **_: ToolResult(tool_name="local::write", status="success"),
        ToolDefinition(
            name="local::write",
            read_only=False,
            risk_level="confirm",
            required_permission="tool.write",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        ),
    )
    return registry


def _authorize(step: PlanStep, principal: PermissionPrincipal):
    return StaticPermissionPolicy().authorize(
        plan=Plan(goal="test", steps=[step]),
        principal=principal,
        tool_registry=_registry(),
        retrieval_scope=None,
        run_id="run_test",
        conversation_id="conv_test",
    )


def test_safe_search_is_allowed():
    report = _authorize(
        PlanStep(id="s1", kind="search", query="鸡肉安全"),
        PermissionPrincipal(),
    )

    assert report.decisions[0].decision == "allow"


def test_write_tool_requires_confirmation_when_scope_and_permission_match():
    report = _authorize(
        PlanStep(id="s1", kind="tool", tool_name="local::write", arguments={"path": "demo.md"}),
        PermissionPrincipal(
            permissions=["tool.write"],
            tool_allowlist=["local::*"],
        ),
    )

    assert report.decisions[0].decision == "confirm"


def test_schema_error_is_denied_before_risk_decision():
    report = _authorize(
        PlanStep(id="s1", kind="tool", tool_name="local::write", arguments={}),
        PermissionPrincipal(
            permissions=["tool.write"],
            tool_allowlist=["local::*"],
        ),
    )

    assert report.decisions[0].decision == "deny"
    assert report.decisions[0].validation_errors
