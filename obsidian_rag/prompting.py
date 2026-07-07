from __future__ import annotations

from obsidian_rag.schema import SearchResult
from obsidian_rag.debugging import debug_breakpoint

SYSTEM_PROMPT = """你是一个基于本地知识库回答问题的 RAG 助手。
请只基于给定资料回答；如果资料不足，明确说明资料不足。
回答要尽量具体，并在关键结论后标注来源编号，例如 [S1]。
回答末尾必须列出：

**使用到的来源：**
KB-072：不建议清洗生鸡肉；KB-073/074 相关清洁与洗手内容
KB-071：交叉污染常见路径；KB-072：不建议清洗生鸡肉

来源汇总规则：
- 优先使用资料里的 chunk_id 和 topic/title，格式为「KB-072：主题」。
- 多个 chunk 支撑同一类结论时，可以合并到同一行，用分号分隔。
- 只能列出实际用到的资料，不要编造资料里不存在的 KB 编号。"""


def build_rag_messages(question: str, results: list[SearchResult]) -> list[dict[str, str]]:
    context_blocks = []
    for index, result in enumerate(results, start=1):
        label = f"[S{index}] {_format_source_label(result)}"
        context_blocks.append(f"{label}\n{result.chunk.text}")

    context = "\n\n---\n\n".join(context_blocks) if context_blocks else "未检索到相关资料。"
    user_content = f"""问题：
{question}

资料：
{context}

请基于资料回答，并在最后列出使用到的来源。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    debug_breakpoint("prompting.messages_built", question=question, messages=messages)
    return messages


def format_sources(results: list[SearchResult]) -> list[str]:
    sources: list[str] = []
    seen: set[str] = set()
    for result in results:
        source = str(result.chunk.metadata.get("source", "unknown"))
        if source not in seen:
            sources.append(source)
            seen.add(source)
    return sources


def _format_source_label(result: SearchResult) -> str:
    metadata = result.chunk.metadata
    chunk_id = metadata.get("chunk_id")
    topic = metadata.get("topic") or metadata.get("title")
    source = metadata.get("source", "unknown")

    if chunk_id and topic:
        return f"{chunk_id}：{topic}"
    if chunk_id:
        return str(chunk_id)
    if topic:
        return f"{source} ({topic})"
    return str(source)
