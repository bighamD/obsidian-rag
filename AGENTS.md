# AGENTS.md

## 默认沟通

- 默认用中文回答。
- 命令、文件名、配置项、API 名称保留英文原文。
- 解释学习概念时优先结合本仓库已有版本：`v0`、`v1`、`v2`、`v3`、`v3_1`、`v3_2`、`v3_3`、`v3_4`。

## 新增版本的固定要求

每次新增一个学习版本时，保持独立版本目录和完整学习闭环。

必须包含：

- 独立目录，例如 `obsidian_rag/v3_5/`。
- FastAPI app，Swagger 可测试 JSON 接口。
- CLI 调试入口，例如 `obsidian-rag agent-v3-5 ...`。
- VS Code/Cursor `launch.json` 调试配置。
- 单元测试，至少覆盖 service、API、CLI。
- 学习文档，说明新版本比上一版本改进了什么。
- SVG 流程图，帮助理解当前版本主流程。
- 文件职责说明，解释新增目录里每个文件的作用。
- 断点调试说明，指出应该在哪些文件和函数打断点。

默认接口要求：

- 当前优先返回 JSON response。
- 暂不默认实现 SSE，除非用户明确要求。
- Swagger payload 要在文档中给出可直接测试的示例。

## 版本边界

新增版本必须说清楚：

- 当前版本做什么。
- 当前版本不做什么。
- 相比上一版本新增了什么能力。
- 下一版本大概率会补什么能力。

如果某个版本只是 planner、router、eval 或其他局部能力，不要偷偷接入完整 RAG 流程。必须在文档和图里明确边界。

## 文档图片风格

后续 SVG 图优先参考：

```text
docs/assets/rag-v3-4-planner-flow.svg
```

推荐风格：

- 使用三栏或分区结构表达：输入、核心流程、输出。
- 核心流程用编号节点表示，节点名称和代码函数/graph node 对齐。
- 用底部提示条明确版本边界，例如“不执行检索”“不生成最终答案”。
- 少用交叉箭头，避免读图时来回跳。
- 背景使用浅色，主要区域用白底卡片，边框颜色区分语义。
- 标题要直接说明版本和流程，例如 `V3.4 Planner 流程`。
- 图里的文字要短，避免塞长段解释；详细解释放到 Markdown 文档。

不推荐：

- 只有横向盒子串联，没有说明版本边界。
- 箭头交叉过多。
- 把实现细节、学习目标、下一版本内容混在同一块里。
- 图片里出现过多中英文长句导致难读。

## 当前版本学习路线

已完成到：

```text
V3.4 LangGraph Planner
```

当前 V3.4 只做 planner 拆解：

```text
build_prompt -> call_planner -> parse_plan
```

V3.4 不会执行 RAG：

- 不调用 `RetrievalService.search()`。
- 不查 Qdrant。
- 不做 hybrid retrieval。
- 不生成最终 RAG answer。

下一阶段建议：

```text
V3.5 Planner Executor
```

V3.5 再考虑把 `plan.steps[]` 里的 `search` / `synthesize` 真正执行起来。

## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Name a file or symbol in the query to read its current line-numbered source. If it's listed but deferred, load it by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` prints the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
