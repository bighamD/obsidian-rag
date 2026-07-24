## ADDED Requirements

### Requirement: 模型窗口驱动的 Context 管理
系统 SHALL 根据当前模型 Profile、估算 token 和配置阈值触发 DeepAgents Offloading/Summarization，MUST NOT 使用固定 `memory_window` 或固定对话轮数作为唯一压缩依据。

#### Scenario: 短会话不触发摘要
- **WHEN** 当前线程 Context 低于配置阈值
- **THEN** 系统保留原始近期 messages 且不创建不必要的 Summary

#### Scenario: 长会话触发摘要
- **WHEN** 当前线程 Context 接近模型窗口阈值
- **THEN** 系统压缩或卸载较旧内容，并继续完成当前请求而不因 Context 过长失败

### Requirement: Summary 保留关键执行信息
Summary SHALL 保留继续任务所需的目标、用户约束、已确认决定、未完成事项、Artifact 引用和关键 Tool Observation；近期 messages SHALL 尽量保留原文。

#### Scenario: 摘要后继续 Artifact 任务
- **WHEN** 长会话在生成文件任务中触发摘要
- **THEN** 后续模型调用仍能识别目标文件、已确认内容、Artifact 状态和下一步操作

### Requirement: 大 Tool Result Offloading
系统 SHALL 允许将超过阈值的 Tool Result 卸载到受控 Backend，并在 messages 中保留可恢复的引用与必要摘要。

#### Scenario: 检索结果过长
- **WHEN** `search_notes` 或其他 Tool 返回超过 Context 策略阈值的结果
- **THEN** 系统避免把全部原文永久堆积在 Prompt 中，同时保留回答所需证据和可追踪引用

### Requirement: Context 数据语义可区分
API schema、Swagger 和 Console MUST 区分原始 Thread messages、Context Summary、长期 Memory、知识库 chunk、当前 Prompt Context 调试信息和仅用于前端兼容的响应投影。

#### Scenario: 查看 Context Inspector
- **WHEN** 用户查看一次 V3.17 Run 的 Context 面板
- **THEN** 每类数据均显示来源、是否进入当前模型 Context 和生命周期，不把兼容投影视为精确 Wire Prompt

### Requirement: Summary 可配置与可观察
系统 SHALL 暴露 Summary 是否启用、触发阈值、触发次数、压缩前后估算 token 和安全摘要元数据，并 SHALL 支持调试环境使用较小阈值构造触发案例。

#### Scenario: 调试摘要触发
- **WHEN** 用户以调试配置连续提交足够长的同线程消息
- **THEN** JSON/SSE 和 Console 能观察到 Summary 触发及压缩前后变化，而不展示隐藏 chain-of-thought

