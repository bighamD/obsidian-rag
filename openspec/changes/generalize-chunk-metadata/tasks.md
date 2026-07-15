## 1. 通用结构化 metadata

- [x] 1.1 新增共享 Markdown 标题块 / fenced YAML metadata 提取与规范化 helper。
- [x] 1.2 为任意 `chunk_id`、标题别名、来源和 tags 合并补充单元测试。

## 2. 两条切片路径接入

- [x] 2.1 将 legacy Markdown chunker 改为基于结构化标题块分段，并保留通用编号标题 fallback。
- [x] 2.2 将 V3.11.1 Docling adapter 改为按 heading path 回填结构化 metadata。
- [x] 2.3 覆盖 VU ID、旧 KB ID、无 YAML 和多子 chunk 的回归测试。

## 3. 对外说明与验证

- [x] 3.1 更新 V3.11.1 Swagger 字段说明和学习文档，明确业务 ID 不限 KB 前缀及需要重新 ingest。
- [x] 3.2 运行相关单元测试、真实 VueUse chunks preview smoke 与静态检查。
