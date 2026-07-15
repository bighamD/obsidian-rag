from fastapi import FastAPI

from obsidian_rag.v3_11_1.routes import documents, health, runtime


app = FastAPI(
    title="Obsidian RAG V3.11.1 Docling Structured Ingestion API",
    version="v3.11.1",
    description=(
        "使用 Docling DocumentConverter 与 HybridChunker 学习多格式解析、"
        "DoclingDocument、contextualized chunk 和共享 Qdrant ingest。"
    ),
)

app.include_router(health.router)
app.include_router(runtime.router)
app.include_router(documents.router)
