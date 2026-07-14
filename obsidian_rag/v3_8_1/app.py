from __future__ import annotations

from fastapi import FastAPI

from obsidian_rag.v3_8_1.routes import agent, health, memory

app = FastAPI(
    title="Obsidian RAG V3.8.1 Conversation Memory API",
    version="v3.8.1",
    description="Conversation Memory API that keeps raw MySQL turns and compacts older context into a rolling summary.",
)

app.include_router(health.router)
app.include_router(agent.router)
app.include_router(memory.router)
