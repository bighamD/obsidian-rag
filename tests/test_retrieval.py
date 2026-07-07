from obsidian_rag.embeddings import HashEmbeddingClient, parse_ollama_embeddings
from obsidian_rag.memory_store import InMemoryVectorStore
from obsidian_rag.schema import TextChunk


def test_in_memory_vector_store_returns_most_similar_chunks_first():
    embeddings = HashEmbeddingClient(dimensions=32)
    store = InMemoryVectorStore(embedding_dimensions=32)
    chunks = [
        TextChunk(text="Python virtual environments and package installs", metadata={"source": "python.md"}),
        TextChunk(text="Agent memory uses retrieval augmented generation", metadata={"source": "agent.md"}),
        TextChunk(text="Coffee brewing notes", metadata={"source": "coffee.md"}),
    ]
    store.upsert(chunks, embeddings.embed_texts([chunk.text for chunk in chunks]))

    results = store.search(embeddings.embed_query("How does agent retrieval memory work?"), top_k=2)

    assert [result.chunk.metadata["source"] for result in results] == ["agent.md", "python.md"]
    assert results[0].score > results[1].score


def test_parse_ollama_embeddings_accepts_batch_response():
    response = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

    assert parse_ollama_embeddings(response) == [[0.1, 0.2], [0.3, 0.4]]


def test_parse_ollama_embeddings_accepts_legacy_single_response():
    response = {"embedding": [0.1, 0.2]}

    assert parse_ollama_embeddings(response) == [[0.1, 0.2]]
