## ADDED Requirements

### Requirement: 结构化业务 chunk metadata 提取
系统 SHALL 从 Markdown 标题块内包含 `chunk_id` 的 fenced YAML 提取业务 metadata。`chunk_id` MUST 接受任意非空标量字符串，不得要求 `KB-` 或其他固定前缀。系统 SHALL 保留文件路径 `source`，并将 YAML 的 `source` 暴露为 `kb_source`；系统 SHALL 传播 `title`、`category`、`tags` 和 `topic`，其中未提供 `topic` 时 SHALL 使用 `title` 作为 topic。

#### Scenario: 提取 VU 前缀的 YAML ID
- **WHEN** 一个二级标题块包含 `chunk_id: VU-001` 和 `title: VueUse 定位`
- **THEN** 该块生成的 chunk metadata 包含 `chunk_id: VU-001`、`title: VueUse 定位` 和 `topic: VueUse 定位`

#### Scenario: 保持文件来源与知识来源分离
- **WHEN** 一个标题块 YAML 同时包含 `source: https://vueuse.org/guide/`
- **THEN** chunk metadata 的 `source` 保持源文件路径，且 `kb_source` 为该 URL

### Requirement: Legacy Markdown 结构边界兼容
legacy Markdown chunker SHALL 按包含 YAML `chunk_id` 的二级标题块切分语义边界，并让该块的所有子 chunk 继承同一业务 metadata。没有 YAML 时，系统 SHALL 兼容以通用编号开头的二级标题作为 ID fallback；系统不得把 `KB-` 作为唯一可识别前缀。

#### Scenario: 同一 VU 标题块生成多个子 chunk
- **WHEN** `## VU-002` 标题块含有 `chunk_id: VU-002` 且正文超过长度上限
- **THEN** 该标题块产生的全部子 chunk 均包含 `chunk_id: VU-002`

#### Scenario: 兼容原有 KB 标题
- **WHEN** 旧文档使用 `## KB-072` 标题和 `chunk_id: KB-072`
- **THEN** chunk metadata 仍包含 `chunk_id: KB-072`

### Requirement: Docling HybridChunker metadata 回填
V3.11.1 SHALL 基于 Docling 产出的 heading path 将同一标题块的结构化 metadata 合并到每个 HybridChunker TextChunk。系统 SHALL 保留由 adapter 生成的 `node_id`、`heading_path`、`page_numbers`、`raw_chunk_text` 和 Docling 调试 metadata。

#### Scenario: Docling chunk 使用 YAML 业务 ID
- **WHEN** Docling 转换的 Markdown 标题块含有 `chunk_id: VU-001` 且 HybridChunker chunk 的 heading path 指向该标题
- **THEN** 返回的 TextChunk metadata 同时包含 `node_id` 和 `chunk_id: VU-001`

#### Scenario: 无结构化 YAML 的 Docling 文档
- **WHEN** Docling 文档没有包含 `chunk_id` 的标题块 YAML
- **THEN** 系统仍生成 chunks 和 `node_id`，且不会伪造 `chunk_id`
