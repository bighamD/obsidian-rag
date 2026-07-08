from __future__ import annotations

from fastapi import FastAPI

from obsidian_rag.v2.routes import eval, health

app = FastAPI(
    title="Obsidian RAG Evaluation API",
    version="v2",
    description="JSON API for repeatable RAG retrieval evaluation.",
)

app.include_router(health.router)
app.include_router(eval.router)
