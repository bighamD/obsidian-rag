# Debugging RAG Flow In VSCode/Cursor

这份文档说明如何在 VSCode 或 Cursor 里调试当前 RAG v0 流程。

## Debug Configurations

调试配置在：

```text
.vscode/launch.json
```

包含三个入口：

- `RAG ask: harness architecture`
- `RAG search: harness architecture`
- `RAG ingest current vault`

推荐先跑：

```text
RAG ask: harness architecture
```

它会执行：

```bash
.venv/bin/python -m obsidian_rag.cli ask "harness 的架构是什么" --top-k 5
```

## How Breakpoints Work

代码里使用了可开关断点：

```python
debug_breakpoint("ask.before_llm", messages=messages)
```

默认情况下，普通命令不会暂停。

只有设置了环境变量 `RAG_DEBUG_BREAKPOINTS`，对应断点才会触发：

```bash
RAG_DEBUG_BREAKPOINTS=ask.before_llm
```

也可以一次开启多个：

```bash
RAG_DEBUG_BREAKPOINTS=ask.after_retrieval,prompting.messages_built,ask.before_llm
```

或者开启全部：

```bash
RAG_DEBUG_BREAKPOINTS=all
```

## Ask Flow Breakpoints

`RAG ask: harness architecture` 默认开启：

```text
ask.after_retrieval
prompting.messages_built
ask.before_llm
ask.after_llm
```

你会看到：

- 检索出来的 `SearchResult`
- 第一条命中的 source、title、chunk text
- 真正发给 LLM 的 `messages`
- LLM 返回的最终 response

调用链：

```text
cli.py
-> pipeline.answer()
-> pipeline.search()
-> qdrant_store.search()
-> prompting.build_rag_messages()
-> llm.OpenAIChatClient.complete()
```

## Search Flow Breakpoints

`RAG search: harness architecture` 默认开启：

```text
search.after_query_embedding
qdrant.after_search
search.after_retrieval
```

你会看到：

- 用户问题如何变成 query embedding
- query vector 的维度和前几个数值
- Qdrant 返回了多少结果
- top result 的 score 和 metadata

## Ingest Flow Breakpoints

`RAG ingest current vault` 默认开启：

```text
ingest.after_load
ingest.after_chunks
ingest.after_embeddings
qdrant.before_upsert
ingest.after_upsert
```

你会看到：

- `RAG_VAULT_PATH` 下加载了多少文档
- 文档切出了多少 chunks
- embedding 向量维度是否是 1024
- 写入 Qdrant 前的 first chunk
- upsert 后的 collection 和 chunk 数量

## Useful Places To Inspect

- `obsidian_rag/pipeline.py`
  - `ingest_path`
  - `search`
  - `answer`
- `obsidian_rag/prompting.py`
  - `build_rag_messages`
- `obsidian_rag/qdrant_store.py`
  - `upsert`
  - `search`
- `obsidian_rag/llm.py`
  - `complete`

## Normal CLI Still Works

这些断点不会影响普通命令：

```bash
.venv/bin/obsidian-rag ask "harness 的架构是什么"
```

因为普通命令没有设置 `RAG_DEBUG_BREAKPOINTS`。
