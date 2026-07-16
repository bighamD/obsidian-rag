# Agent Console UI 契约里程碑快照

`frontend/agent_console/` 是当前唯一维护的 Agent Console，当前支持：

```text
Console contract: console.v1
Backend: V3.12.1
Port: 8020
```

`snapshots/` 不按照 Swagger 版本逐个复制前端。只有用户可见的请求、响应、SSE 事件或主要交互契约发生不兼容变化时，才冻结上一套可运行 Console。

## 快照准入条件

至少满足一项：

- Console API contract 发生不向后兼容升级，例如 `console.v1 -> console.v2`。
- Agent Console 必须采用新的事件模型或会话交互，无法继续兼容当前实现。
- 为学习目的需要保留两套真实、可运行且可对照的用户体验。

以下变化不产生快照：

- 新增一个 Swagger 学习版本。
- Parser、Chunk、Planner、Tool、MCP 或 Permission 的内部实现变化，但 `console.v1` 保持兼容。
- 样式调整、组件重构、可选字段或向后兼容的新能力。

## 真实性要求

快照必须来自对应 UI 里程碑完成时的真实代码，不允许把当前演进后的 Console 复制并命名为旧版本。本次整理没有选择可信的历史工作树，因此不伪造 V3.10.1、V3.10.2 或 V3.11 快照。

未来每个快照目录必须在自己的 README 中记录：

```text
UI milestone:
Console contract:
Backend version:
Backend port:
Source commit:
Last verified commit:
Maintenance status: frozen
```

冻结快照只修复阻断学习的严重问题；常规体验优化仅进入 `frontend/agent_console/`。
