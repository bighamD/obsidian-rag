from fastapi import FastAPI

from obsidian_rag.v3_11_2.routes import frameworks, health, runtime


app = FastAPI(
    title="Obsidian RAG V3.11.2 Chunking Framework Comparison API",
    version="v3.11.2",
    description=(
        "在同一 Docling 文档和 embedding 上比较 LangChain ParentDocumentRetriever、"
        "LlamaIndex AutoMergingRetriever 与 SemanticSplitterNodeParser。"
    ),
)

app.include_router(health.router)
app.include_router(runtime.router)
app.include_router(frameworks.router)
