## Context

仓库以独立 Swagger 和版本目录记录后端学习过程，但 Vue Agent Console 从 V3.10.1 开始持续演进，目录名和类型依赖仍保留历史版本痕迹。当前前端通过 `VITE_API_TARGET` 可以连接多个端口，却没有在启动时验证后端是否完整提供会话、Run、SSE、答案增量和 reasoning 等契约，导致版本不匹配只能在用户操作时以 404、500 或字段缺失暴露。

这项变更跨越 FastAPI 公共路由、Pydantic schema、Vue API client、会话 composable、调试配置和学习文档，需要先建立一个不随学习版本命名变化的 Console API 边界。

## Goals / Non-Goals

**Goals:**

- 建立稳定、无版本目录的 `console.v1` 后端契约。
- 让当前 Agent Console 只支持 V3.12.1 / 8020，并在启动时验证兼容性。
- 用 capability manifest 描述功能差异，避免把后端版本判断散落到 Vue 组件。
- 用 UI 契约里程碑而不是 Swagger 数量决定是否冻结前端快照。
- 通过后端 contract test 和前端单元测试防止接口再次漂移。

**Non-Goals:**

- 不为每个 Swagger 创建完整前端。
- 不从当前代码反向伪造 V3.10.1、V3.10.2 或 V3.11 历史快照。
- 不要求历史 Swagger 实现 `console.v1`。
- 不改变 Agent 执行、Prompt、检索、Memory、SSE 事件和 reasoning 内容语义。

## Decisions

### 1. Console 契约使用无版本 Python package

新增 `obsidian_rag/console_api/`，集中维护 Console 对外 schema、router 和依赖。V3.12.1 只负责将该 router 挂载到自己的 FastAPI app，不再 import 旧学习版本的 Console schema/router。

备选方案是继续在每个版本中复制 router，但会重复制造 Pydantic 类型漂移；另一个备选是让公共层 import 某个学习版本，仍然会倒置依赖方向。

### 2. 使用 `console.v1` 契约版本和能力清单

`GET /console/config` 返回：

- `contract_version`: 固定为 `console.v1`。
- `backend_version`: 当前为 `v3.12.1`。
- `features`: JSON、SSE、answer delta、reasoning delta、conversation memory、collections 等布尔能力。
- `endpoints`: 前端使用的稳定路径。
- `default_memory_window`: 默认 Memory 窗口。

前端只根据契约和能力工作，不根据 `backend_version` 编写业务分支。`backend_version` 仅用于显示和诊断。

### 3. 启动兼容检查由 API client 与 composable 协作完成

`production-client.ts` 负责请求并解析 manifest；`use-agent-console.ts` 保存兼容状态并阻止不兼容后端上的业务请求；`App.vue` 只组合并展示明确错误。现有聊天、侧栏和 Inspector 组件无需感知 Swagger 版本。

### 4. 当前前端去版本化，历史快照按规则冻结

将当前目录改为 `frontend/agent_console/`。新增 `frontend/snapshots/README.md` 记录准入规则：只有请求/响应、事件模型或主要交互发生不向后兼容的实质变化时才冻结快照；内部重构、单个后端工具或仅 Swagger 能力不产生快照。

现有历史代码没有可信的独立工作树，因此本次不回填快照。以后冻结时从对应里程碑完成提交复制，并在快照 README 中记录后端版本、契约和最后验证 commit。

### 5. 调试入口只表达当前支持关系

`.vscode/launch.json` 保留各版本 API server，但只保留一个 Agent Console UI 配置，工作目录为 `frontend/agent_console`，默认代理到 8020。Swagger 仍可独立启动，不再暗示当前 Console 能连接所有版本。

## Risks / Trade-offs

- [目录重命名导致文档或脚本路径失效] → 全仓检索旧目录名，并通过前端 build 与 launch 配置检查验证。
- [能力清单与真实接口再次漂移] → 对 manifest、会话读取和关键 endpoint 增加同一组 contract tests。
- [不兼容页面完全阻止旧 Swagger 学习] → 旧版本仍可使用 Swagger/CLI；历史 UI 学习通过以后真实冻结的 snapshot 完成。
- [公共 Console 层过早承载过多业务] → 只放前端稳定 DTO、能力协商和 Console 专属路由，不移动 Agent Runtime 实现。
- [reasoning 开关是运行配置而非静态能力] → manifest 同时表达“协议支持”和当前启用状态，前端仍以实际事件为准。

## Migration Plan

1. 新增 `console_api` schema/router/dependency 和 contract tests。
2. V3.12.1 切换到公共 Console router，验证真实 MySQL 会话。
3. 重命名前端目录并更新 package、Vite、文档和 launch 路径。
4. 前端增加 manifest 类型、请求、启动校验和不兼容状态测试。
5. 增加 snapshots 规则文档，并全仓清理当前 UI 指向旧目录/旧端口的配置。
6. 若需回滚，可恢复旧前端目录名并让 V3.12.1 临时挂载自身 Console router；数据库和 Agent 数据不需要迁移。

## Open Questions

- `console.v2` 何时产生：暂定只有出现无法通过新增可选字段兼容的 UI 契约变化时升级。
- 是否未来发布独立 npm package 共享前端 contract types：当前学习仓库规模不需要，先保持 TypeScript 本地类型与后端 contract tests 对齐。
