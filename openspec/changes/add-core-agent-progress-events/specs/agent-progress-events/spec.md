## ADDED Requirements

### Requirement: 公共 Agent Progress contract
Core SHALL 发布与 LangGraph 节点名称解耦的 `progress` 事件，每个事件 MUST 包含稳定 phase 和 running/completed/failed status。

#### Scenario: 检索开始
- **WHEN** Agent 开始执行初始检索或补搜
- **THEN** Core 发布 phase=retrieval、status=running，并包含实际 collection

#### Scenario: 检索完成
- **WHEN** 检索步骤完成
- **THEN** Core 发布 phase=retrieval、status=completed，并包含聚合 result_count

### Requirement: Progress 与调试事件分离
系统 MUST 保留 `trace_event` 作为调试细节，并 SHALL 使用 `progress` 作为面向用户的稳定阶段；progress 不得包含隐藏推理。

#### Scenario: Graph 节点改名
- **WHEN** 内部 LangGraph 节点名称变化但业务阶段不变
- **THEN** 前端仍通过相同 phase 展示状态，无需依赖节点名

### Requirement: Agent Console 当前状态
Agent Console SHALL 在同一个 assistant 气泡中显示最新 progress 文案，并在 `answer_delta` 到达后继续增量显示正文。

#### Scenario: 首 token 前
- **WHEN** Agent 正在执行 memory、planning、retrieval 或 evidence 阶段
- **THEN** 页面显示对应的当前状态，不只显示通用“正在生成回答”

#### Scenario: 旧后端兼容
- **WHEN** SSE 没有发送 progress 但发送 answer_delta
- **THEN** 前端继续正常增量展示答案

### Requirement: 终态运行摘要
回答完成后，Agent Console SHALL 显示 collection、检索结果数、总耗时、TTFT 和 Memory 写入状态的紧凑摘要。

#### Scenario: 成功回答
- **WHEN** 收到 `run_succeeded` 完整响应
- **THEN** 同一 assistant 消息显示最终答案、sources 和运行摘要，不产生重复消息

### Requirement: V3.12.1 UI server
`launch.json` SHALL 仅保留 server 配置，并提供连接 V3.12.1 `8020` 的 Vite Agent Console server。

#### Scenario: VS Code 启动前后端
- **WHEN** 用户分别运行 V3.12.1 API server 和 UI server 配置
- **THEN** Vite `/api` 请求代理到 `http://127.0.0.1:8020`
