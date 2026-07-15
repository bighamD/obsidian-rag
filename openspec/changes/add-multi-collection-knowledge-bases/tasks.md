## 1. Collection 基础设施

- [x] 1.1 在配置层实现 collection 名称校验和不可变的请求级 config 覆盖。
- [x] 1.2 将 KeywordIndex 路径改为 collection-scoped，并覆盖隔离行为。

## 2. 共享检索与 V0 服务面

- [x] 2.1 让 pipeline、dense retrieval 与 keyword/hybrid retrieval 使用同一个请求 collection。
- [x] 2.2 为 V0 ingest/search/compare-search/ask 的 schema、服务和 JSON response 接入 collection。
- [x] 2.3 为 V0 CLI 增加 `--collection`，并覆盖默认值、显式值和非法值。

## 3. V3.11.1 与 Agent 贯通

- [x] 3.1 为 V3.11.1 Docling ingest/search API、CLI 和 response 接入 collection。
- [x] 3.2 让 V3.8.1 Agent 与 V3.11 Skill Agent 的初始检索、retry 检索使用同一 collection。

## 4. 学习闭环与验证

- [x] 4.1 更新 README、V3.11.1 学习文档、Swagger 示例和 VS Code 调试案例，说明多 collection 操作与迁移。
- [x] 4.2 新增或更新 service、API、CLI 和 Agent 回归测试，验证两个 collection 的 dense/keyword/hybrid 隔离。
- [x] 4.3 运行聚焦测试、静态检查、OpenSpec strict 校验和本地多 collection smoke。
