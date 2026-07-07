from __future__ import annotations

from fastapi import FastAPI

from obsidian_rag.v1.routes import ask, health, ingest, search

app = FastAPI(
    title="Obsidian RAG API",
    version="v1",
    description="JSON API for testing Obsidian RAG retrieval and answers.",
)

app.include_router(health.router)
app.include_router(search.router)
app.include_router(ask.router)
app.include_router(ingest.router)
