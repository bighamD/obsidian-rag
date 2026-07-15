from obsidian_rag.qdrant_store import QDRANT_UPSERT_BATCH_SIZE, QdrantVectorStore
from obsidian_rag.schema import TextChunk


class FakeQdrantClient:
    def __init__(self):
        self.batches = []

    def upsert(self, collection_name, points):
        self.batches.append((collection_name, list(points)))


def test_upsert_splits_large_point_sets_into_batches():
    store = object.__new__(QdrantVectorStore)
    store.client = FakeQdrantClient()
    store.collection_name = "recipes"
    chunks = [
        TextChunk(text=f"recipe-{index}", metadata={"source": "recipes.md", "chunk_index": index})
        for index in range(QDRANT_UPSERT_BATCH_SIZE * 2 + 1)
    ]
    vectors = [[float(index), 0.0] for index in range(len(chunks))]

    store.upsert(chunks, vectors)

    assert [len(points) for _, points in store.client.batches] == [128, 128, 1]
    assert {collection for collection, _ in store.client.batches} == {"recipes"}
