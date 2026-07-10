from __future__ import annotations

from fastapi import FastAPI

from obsidian_rag.v3_8.routes import agent, health, memory

app = FastAPI(
    title="Obsidian RAG V3.8 Conversation Memory API",
    version="v3.8",
    description="Conversation Memory API that persists raw turns in SQLite and loads a bounded recent-history window.",
)

app.include_router(health.router)
app.include_router(agent.router)
app.include_router(memory.router)
