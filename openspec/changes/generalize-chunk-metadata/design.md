## Context

旧的 Markdown chunker 用 `KB-...` 二级标题识别语义块；V3.11.1 Docling adapter 则用同样前缀的正则从标题和文本中回填 `chunk_id`。这把食品安全示例的业务 ID 格式误当成了系统契约。新 VueUse 知识库已在每个标题块的 fenced YAML 中提供 `chunk_id: VU-001`、`title`、`category`、`tags` 和 `source`，但这些元数据未能稳定传播到检索结果。

`node_id` 已经是系统生成的稳定向量 ID；`chunk_id` 应是可选的人类/业务引用。两者不能再使用同一套前缀假设。

## Goals / Non-Goals

**Goals:**

- 从标题块内 fenced YAML 读取通用业务 metadata，不限制 `chunk_id` 前缀。
- 在 legacy 和 Docling 两条路径中一致传播 `chunk_id`、标题、分类、标签和来源。
- 保持 `KB-072` 旧文档、无 YAML 的编号标题及现有检索接口兼容。
- 让下游 Context Builder 继续仅依据 `chunk_id` 是否存在排序，不感知前缀变化。

**Non-Goals:**

- 不修改 Docling 的解析、OCR、版面分析或 HybridChunker 算法。
- 不自动迁移已经写入 Qdrant 的旧 payload；需要用户显式重新 ingest。
- 不把任意代码块 YAML 都当 metadata；只绑定到有对应 Markdown 标题的结构块。
- 不为非 Markdown 源文件虚构业务 metadata。

## Decisions

### 1. 以 fenced YAML 为业务 metadata 的权威来源

新增一个共享 metadata helper，识别标题后的 fenced YAML，并用 `yaml.safe_load` 读取。`chunk_id` 只要求是非空标量字符串，因此 `KB-072`、`VU-001`、`RFC-9457` 等均可用。`source` 映射到 `kb_source`，避免覆盖文件路径 `source`；`tags` 规范化并和文件 tags 合并；`topic` 优先使用 YAML 的 `topic`，缺失时使用 YAML `title`。

选择该方案而非扩展正则为 `(KB|VU)-...`，因为前缀枚举会随着新知识域不断失效，也无法可靠读取分类、标签和来源。

### 2. 结构边界由标题与元数据决定，而不是 ID 前缀

legacy chunker 将有 `chunk_id` YAML 的二级标题视为一个完整语义块，保证它的所有子 chunk 继承同一 metadata。没有 YAML 时，保留通用 `ABC-123` 风格标题编号的兼容 fallback；不再把 `KB` 作为特殊前缀。没有可识别结构块的文档继续使用原有整文档段落切分行为。

### 3. Docling 根据 heading path 回填 metadata

Docling 仍负责解析和结构化切片。adapter 从 `conversion.markdown` 建立“标题别名 → metadata”映射，别名包含 Markdown 标题、YAML `title` 和去除可选编号前缀后的标题文本。对每个 HybridChunker output，按最深的 `heading_path` 命中一条 metadata，再合并到其 payload。这样既不重写 Docling，也使同一结构标题下的多个框架 chunk 获得相同业务 metadata。

### 4. 保持稳定 ID 与业务 ID 分离

`node_id` 仍由 source、chunk index 和 contextualized text 生成，供 Qdrant 去重和 point ID 使用。`chunk_id` 仅用于引用、展示、上下文排序和评测，缺失时不阻断 chunk 生成。

## Risks / Trade-offs

- [Docling 导出的 Markdown 未保留原 fenced YAML] → 不回填业务 metadata，但 chunking 主链路不受影响；通过测试和本地 VueUse smoke 验证。
- [同一标题名称重复] → 优先匹配最深 heading，并以文档顺序的最后一个完全匹配项为准；建议知识库标题在同一文件内保持唯一。
- [业务 YAML 与示例代码块混淆] → 只接受标题块内且包含 `chunk_id` 的 YAML 映射。
- [旧索引 payload 没有新 metadata] → 文档中明确要求重新 ingest；不做隐式重建。
