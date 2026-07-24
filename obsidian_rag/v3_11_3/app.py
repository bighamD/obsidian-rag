from fastapi import FastAPI

from obsidian_rag.v3_11_3.routes import collections, health


app = FastAPI(
    title="Obsidian RAG V3.11.3 Collection Router API",
    version="v3.11.3",
    description="Knowledge Base Registry、显式优先 Collection Router、多库 Hybrid Retrieval 和跨库 RRF JSON API。",
)

app.include_router(health.router)
app.include_router(collections.router)
