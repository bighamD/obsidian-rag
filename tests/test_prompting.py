from obsidian_rag.prompting import build_rag_messages, format_sources
from obsidian_rag.schema import SearchResult, TextChunk


def test_build_rag_messages_includes_question_context_and_source_ids():
    results = [
        SearchResult(
            chunk=TextChunk(text="RAG retrieves external notes before answering.", metadata={"source": "rag.md"}),
            score=0.91,
        )
    ]

    messages = build_rag_messages("What is RAG?", results)

    assert messages[0]["role"] == "system"
    assert "只基于给定资料" in messages[0]["content"]
    assert "What is RAG?" in messages[1]["content"]
    assert "[S1] rag.md" in messages[1]["content"]
    assert "RAG retrieves external notes" in messages[1]["content"]


def test_build_rag_messages_exposes_chunk_ids_for_source_summary():
    results = [
        SearchResult(
            chunk=TextChunk(
                text="不建议清洗生鸡肉，以免水花造成交叉污染。",
                metadata={
                    "source": "food.md",
                    "chunk_id": "KB-072",
                    "topic": "不建议清洗生鸡肉",
                },
            ),
            score=0.91,
        )
    ]

    messages = build_rag_messages("生鸡肉还需要清洗下锅吗", results)

    assert "**使用到的来源：**" in messages[0]["content"]
    assert "KB-072：不建议清洗生鸡肉" in messages[0]["content"]
    assert "[S1] KB-072：不建议清洗生鸡肉" in messages[1]["content"]


def test_format_sources_deduplicates_sources():
    results = [
        SearchResult(chunk=TextChunk(text="one", metadata={"source": "rag.md"}), score=0.8),
        SearchResult(chunk=TextChunk(text="two", metadata={"source": "rag.md"}), score=0.7),
        SearchResult(chunk=TextChunk(text="three", metadata={"source": "agent.md"}), score=0.6),
    ]

    assert format_sources(results) == ["rag.md", "agent.md"]
