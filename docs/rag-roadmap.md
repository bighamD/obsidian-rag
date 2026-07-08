# Obsidian RAG Learning Roadmap

This document preserves the project plan so future sessions can recover context quickly after compaction.

## Project Intent

Build a local RAG learning project around the user's Obsidian knowledge base. The focus is RAG itself, not a complex agent framework at the start.

Primary learning question:

> Given a local knowledge base, can the system reliably retrieve the right evidence, use it to answer, and show sources?

## Current Decisions

- Language: Python.
- Initial interface: CLI.
- Knowledge sources: Obsidian Markdown first, PDF second.
- Vector store: Docker Qdrant by default, with embedded local Qdrant as fallback.
- Chat LLM: user's local OpenAI-compatible cliproxy endpoint.
- Embedding: local Ollama with `qwen3-embedding:0.6b`.
- Agent framework: none for v0-v2. Add agent orchestration only in v3.

Known local endpoint:

```text
OPENAI_BASE_URL=http://127.0.0.1:8317/v1
```

Known test result:

- `/v1/models` on cliproxy is reachable.
- Chat model list includes models such as `gpt-5.4-mini`.
- `/v1/embeddings` with `text-embedding-3-small` returned `404 page not found`.
- Therefore `RAG_EMBED_PROVIDER=openai` is not usable with the current cliproxy unless cliproxy adds an embeddings route/model mapping.
- Local Ollama has `qwen3-embedding:0.6b`, embedding dimension `1024`, capability `embedding`.
- Docker Qdrant is available at `http://127.0.0.1:6333` and can be inspected at `http://127.0.0.1:6333/dashboard`.

## Version Plan

### v0: Local Markdown/PDF RAG With Sources

Goal:

Build the smallest complete RAG pipeline:

```text
Obsidian/PDF -> load -> chunk -> embed -> store -> retrieve -> prompt -> LLM answer -> sources
```

User-facing commands:

```bash
obsidian-rag ingest --recreate
obsidian-rag search "query" --top-k 5
obsidian-rag ask "question" --top-k 5
```

`ingest` defaults to `RAG_VAULT_PATH` from `.env`; a CLI path can still override it.

What this version teaches:

- Offline indexing vs runtime retrieval/generation.
- Markdown/PDF loading.
- Obsidian metadata extraction: frontmatter, title, tags, `[[wikilinks]]`.
- Chunking and overlap.
- Embedding as semantic retrieval input.
- Vector DB basics: collection, vectors, payload, top-k similarity.
- Prompt grounding and source citation.
- Common RAG failure modes: wrong chunks, noisy chunks, missing evidence, hallucinated citations.

Current v0 status:

- Basic Python package and CLI exist.
- Tests exist for loaders, chunking, prompt formatting, and in-memory retrieval.
- Qdrant store supports Docker URL and embedded local path fallback.
- `search` works with temporary hash embedding smoke test.
- Real embedding now uses local Ollama `qwen3-embedding:0.6b`.
- Current `.env` should set `QDRANT_URL=http://127.0.0.1:6333` so `ingest/search/ask` write to Docker Qdrant and the Web UI updates directly.

Next v0 tasks:

- Keep `RAG_EMBED_PROVIDER=ollama`.
- Current model: `qwen3-embedding:0.6b`.
- Optionally add `RAG_EMBED_PROVIDER=sentence_transformers` for `BAAI/bge-m3`.
- Run true end-to-end test:

```text
temporary vault -> local embedding -> Qdrant -> search -> cliproxy chat answer -> sources
```

Recommended v0 acceptance criteria:

- Can index a real Obsidian vault.
- `search` returns relevant chunks with file paths and scores.
- `ask` answers based on retrieved chunks and prints sources.
- If retrieval finds no useful evidence or the top score is below `RAG_MIN_SCORE`, the answer says the local notes are insufficient.
- README explains setup, model configuration, and debugging steps.

### v1: Hybrid Search And Rerank≈

Goal:

Improve retrieval quality. v1 is about "find the right evidence more often."

Add:

- Keyword retrieval, preferably BM25 or full-text search.
- Dense vector retrieval from v0.
- Hybrid fusion, for example RRF.
- Optional reranker after initial recall.
- Better query handling:
  - simple query rewrite,
  - multi-query retrieval,
  - metadata filters by path, tag, or file type.

What this version teaches:

- Dense search vs sparse/keyword search.
- Why embeddings alone miss exact names, commands, IDs, dates, and rare terms.
- Recall vs precision.
- Reranking as a second-stage retrieval step.
- Search quality comparison.

Possible implementation paths:

- Keep Qdrant for dense vectors and add a local BM25 index.
- Or use Qdrant hybrid features later if the chosen embedding stack supports sparse vectors.
- Add `obsidian-rag compare-search "query"` to show vector-only vs keyword-only vs hybrid results.

Recommended v1 acceptance criteria:

- Same query can display dense, keyword, and hybrid result lists.
- Hybrid search improves at least a small manual test set.
- CLI exposes enough scores/source info to debug why something ranked high.
- No LLM needed to evaluate basic retrieval behavior.

### v2: Evaluation Loop

Goal:

Stop judging RAG only by vibe. Add a repeatable evaluation workflow.

Add:

- A small evaluation dataset, stored in repo or user-local data:

```text
question
expected_source_files
optional expected_answer_points
```

- Retrieval metrics:
  - hit rate at k,
  - MRR,
  - source recall.

- Answer metrics:
  - source coverage,
  - groundedness/faithfulness checks,
  - answer relevance.

Possible tools:

- Start with a simple custom evaluator for retrieval.
- Add Ragas later for LLM-based evaluation.

What this version teaches:

- How to know whether chunking/search changes actually helped.
- How to separate retrieval failure from generation failure.
- Why test questions should represent real user workflows.

Recommended v2 acceptance criteria:

- `obsidian-rag eval retrieval eval_set.yaml` reports hit rate and MRR.
- Changing chunk size, embedding model, or hybrid settings can be compared.
- At least 10-20 real questions from the user's Obsidian workflow exist.
- Evaluation output is saved so regressions are visible.

Current v2 status:

- `obsidian_rag/v2/` exists as a separate evaluation package.
- `obsidian-rag eval retrieval eval_sets/retrieval-food-safety.yaml --top-k 5 --mode hybrid` reports hit rate, MRR, and source recall.
- `POST /eval/retrieval` is available from `obsidian_rag.v2.app`.
- `POST /eval/answer` provides deterministic source coverage and answer-point coverage checks for an already generated answer.
- Example retrieval eval set exists at `eval_sets/retrieval-food-safety.yaml`.
- V2 learning guide and diagrams live in `docs/v2-evaluation-guide.md`.

### v3: Agentic RAG

Goal:

Wrap the mature retriever as an agent tool. The agent decides when and how to retrieve.

Add:

- Retriever tool:

```text
search_notes(query, top_k, filters)
```

- Agent orchestration, likely LangGraph.
- Multi-step behavior:
  - decide if local notes are needed,
  - search once,
  - inspect evidence,
  - search again if evidence is insufficient,
  - ask a clarifying question if needed,
  - answer with sources.

What this version teaches:

- Difference between fixed RAG and agentic RAG.
- Tool calling.
- Iterative retrieval.
- Planning and evidence checking.
- When agent autonomy helps and when it adds noise.

Recommended v3 acceptance criteria:

- Agent can answer simple questions with one retrieval.
- Agent can perform multi-hop retrieval for questions spanning multiple notes.
- Agent does not search when the question does not need local knowledge.
- Agent exposes trace/debug output showing tool calls and retrieved sources.

Current v3 status:

- `obsidian_rag/v3/` exists as a lightweight agentic RAG package.
- `POST /agent/ask` is available from `obsidian_rag.v3.app`.
- `obsidian-rag agent ask "..."` runs the same lightweight agent loop from CLI.
- The agent decides `search` vs `no_search`, calls V1 `RetrievalService` as `search_notes`, and returns trace steps.
- Multi-hop teaching behavior exists for common combined questions such as chicken washing plus kitchen cleaning.
- V3 learning guide and diagrams live in `docs/v3-agentic-rag-guide.md`.

### v3.1: LLM Router

Goal:

Replace the V3 rule-based search decision with an LLM router that emits structured JSON.

What this version teaches:

- Intent routing before retrieval.
- Why external realtime questions should not trigger local KB search.
- How to make model decisions machine-readable with JSON.
- How to degrade safely when router JSON is invalid.

Current v3.1 status:

- `obsidian_rag/v3_1/` exists as a separate LLM-router package.
- `POST /agent/ask` is available from `obsidian_rag.v3_1.app`.
- `RouterService` asks the LLM to output `search`, `no_search`, or `clarify`.
- `AgentService` executes the structured `RouterDecision` and returns `router` plus `trace`.
- V3.1 learning guide and diagrams live in `docs/v3-1-llm-router-guide.md`.

### v3.2: Tool Calling

Goal:

Let the model choose tools directly instead of only returning a router JSON object.

Possible tools:

- `search_notes`
- `no_search`
- `clarify`

Current v3.2 status:

- `obsidian_rag/v3_2/` exists as a separate tool-calling package.
- `POST /agent/ask` is available from `obsidian_rag.v3_2.app`.
- `obsidian-rag agent-v3-2 ask "..."` runs the same tool-calling loop from CLI.
- `OpenAIChatClient.complete_with_tools()` parses OpenAI/Ollama-compatible `tool_calls`.
- The agent executes `search_notes`, `no_search`, or `clarify` based on `tool_calls[].function.name`.
- V3.2 learning guide and diagrams live in `docs/v3-2-tool-calling-guide.md`.

### v3.3: LangGraph

Goal:

Move the agent workflow into graph nodes such as router, search, evidence check, answer, and clarify.

### v4: Personal Knowledge Assistant

Goal:

Turn the RAG pipeline into a useful daily Obsidian assistant.

Possible features:

- Lightweight local web UI or TUI.
- Source preview with file path and chunk text.
- Obsidian URI links back to notes.
- Conversation history.
- Saved useful answers as Markdown.
- Note synthesis:
  - "summarize my notes on X",
  - "find contradictions",
  - "make a reading path",
  - "cluster related notes",
  - "suggest missing links".

Advanced additions:

- Incremental indexing based on modified files.
- Watch mode for vault updates.
- Permissions or scoped vaults if multiple knowledge bases exist.
- Graph-aware retrieval using Obsidian wikilinks.
- Optional GraphRAG experiment for relationship-heavy notes.

What this version teaches:

- Productizing RAG beyond a demo.
- Incremental indexing.
- Human-in-the-loop knowledge management.
- Turning retrieval results into knowledge workflows.

Recommended v4 acceptance criteria:

- Daily-use interface can search and ask over the real vault.
- Answers link back to original notes.
- Index can update without full rebuild.
- User can inspect and correct weak retrieval results.
- The assistant helps create or update Obsidian notes without hiding sources.

## Technical Notes

### Embedding Provider Options

Priority order:

1. Ollama local embedding.
   - Recommended first model: `nomic-embed-text`.
   - Good for free local RAG learning.
   - Add project support via Ollama `/api/embed` or `/api/embeddings`, depending on local Ollama version.

2. Sentence Transformers local embedding.
   - Recommended model: `BAAI/bge-m3`.
   - Better multilingual/Chinese retrieval potential.
   - Heavier dependencies.

3. Free cloud embedding provider.
   - Jina AI can be considered if local setup is inconvenient.
   - Less ideal for private Obsidian notes.

### Data Safety

- Do not commit `.env`.
- Do not commit local vector DB contents under `.rag/`.
- Treat Obsidian vault content as private local data.
- Avoid writing API keys into docs, tests, or shell scripts.

### Suggested Learning Rhythm

For every version:

1. Make the feature work on a tiny temporary vault.
2. Run it on a small subset of real Obsidian notes.
3. Inspect retrieved chunks before trusting generated answers.
4. Add one or two tests for behavior that should not regress.
5. Update this roadmap with status and surprises.

## Current Recovery Checklist

If a future session starts from this file:

1. Read `README.md`.
2. Read this roadmap.
3. Read `docs/obsidian-rag-code-guide.md` for current module responsibilities and diagrams.
4. Check `.env.example`.
5. Run:

```bash
.venv/bin/python -m pytest
.venv/bin/obsidian-rag --help
```

6. Continue v0 by adding a free local embedding provider, most likely Ollama.
