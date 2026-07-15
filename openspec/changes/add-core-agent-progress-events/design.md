## Context

Core 当前发布 `node_finished`、`trace_event` 和 `answer_delta`。底层节点事件适合调试，但前端若直接映射 `execute_steps` 等节点名，会与 LangGraph 结构耦合；同时缺少节点开始事件，无法准确显示“正在检索”。

## Goals / Non-Goals

**Goals:**

- 用稳定的 phase/status contract 表示面向用户的运行阶段。
- 让 V3.12.1 首 token 前持续提供真实进度。
- 为 V3.13 Permission、V3.14 Sandbox、V3.15 HITL 留出可扩展 phase。
- 保持 trace 和 answer delta 的现有职责。

**Non-Goals:**

- 不把中文 UI 文案写入 Core。
- 不接入 V3.11 Skill Runtime。
- 不实现复杂工作流画布、动画或完整节点时间线。
- 不改变 Agent 执行顺序和耗时。

## Decisions

### 1. 增加独立 progress 事件

Core 发布 `progress`，payload 使用 `phase`、`status`、`collection`、`result_count` 和可选 metadata。`trace_event` 继续用于开发调试，`answer_delta` 继续承载答案文本。

### 2. Core 维护节点到稳定 phase 的映射

节点映射为：load/compact memory→memory，planner→planning，execute/retry→retrieval，evidence_check→evidence，build_context→context，synthesize_answer→answer，save_memory→memory_write。未来 Graph 改名只需更新 Core 映射，前端 contract 不变。

### 3. started 在 timed node 内发布，completed 在 values stream 后发布

`_timed_node` 能在 handler 前发送 running；`ask_with_events` 在节点完成后发送 completed。检索完成事件从 trace/State 汇总 result_count，避免前端猜测。

### 4. 前端只维护当前状态和最终摘要

assistant 草稿增加 currentProgress；progress reducer 根据 phase/status 生成中文文案。收到 answer delta 后保留“正在生成回答”，终态显示 collection、结果数、总耗时、TTFT 和 Memory 状态。

## Risks / Trade-offs

- [同一阶段多个 search step] → 本版显示聚合状态和累计结果数，不构建复杂子任务树。
- [事件重复] → reducer 以最新 phase/status 覆盖单行状态。
- [旧后端没有 progress] → 继续显示“正在生成回答…”并兼容 answer_delta。
- [Core 文案耦合] → Core 只发送枚举和事实，中文映射仅在前端。
