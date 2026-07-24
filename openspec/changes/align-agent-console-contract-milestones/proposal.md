## Why

当前唯一的 Vue Agent Console 虽以 V3.10.1 命名，却先后连接多个学习版本 Swagger，并隐式依赖这些版本接口的并集，已经产生 404、跨版本 Pydantic schema 500 和启动配置含义不清等版本漂移。现在需要把“后端学习版本”和“前端 UI 契约里程碑”分开，让当前前端只连接一个明确、可验证的稳定契约。

## What Changes

- 将当前维护中的前端从 `frontend/v3_10_1_agent_console/` 去版本化为 `frontend/agent_console/`，明确只连接当前 V3.12.1 / 8020 主线。
- 引入 `console.v1` 能力协商响应，公开后端版本、契约版本、支持的功能和稳定端点。
- 前端启动时校验 Console 契约；连接错误 Swagger 时显示明确的不兼容状态，不再等到具体操作才出现 404/500。
- 抽取无版本号的稳定 Console API schema/router，避免 V3.12.1 继续跨版本复用 V3.10.2、V3.10.1 或 V3.8.1 的响应模型。
- 建立 `frontend/snapshots/` 的 UI 契约里程碑规则：仅在用户交互契约发生实质变化时冻结快照，不为每个 Swagger 复制前端，也不使用当前代码伪造历史版本。
- 整理 `launch.json` 和文档，只保留一个当前 Agent Console 启动入口指向 8020；旧 Swagger 继续用于独立学习和调试，不承诺兼容当前前端。
- 增加后端 Console contract 测试和前端兼容检查测试。

## Capabilities

### New Capabilities

- `agent-console-contract-milestones`: 稳定 `console.v1` API、前端启动能力协商、当前 Console 唯一后端边界，以及按 UI 契约里程碑冻结前端快照的规则。

### Modified Capabilities

- 无；仓库尚未建立稳定 Agent Console 契约的公共 OpenSpec capability。

## Impact

- 后端：新增无版本号 Console API 层，V3.12.1 改为挂载稳定 router 和 schema。
- 前端：目录重命名、API 类型与启动状态调整，业务组件和现有会话交互保持不变。
- 调试：`.vscode/launch.json` 的当前 UI 配置统一指向 `frontend/agent_console` 和 V3.12.1 / 8020。
- 测试：增加契约版本、能力字段、会话快照和不兼容后端提示覆盖。
- 文档：说明 Swagger 学习版本与 UI 契约里程碑的独立版本策略。
- 非目标：不回填无法保证真实性的 V3.10.1/V3.10.2/V3.11 前端副本，不删除历史 Swagger，不改变 Agent、Prompt、检索、Memory 或 SSE 事件语义。
