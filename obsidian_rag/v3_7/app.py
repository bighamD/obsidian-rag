from __future__ import annotations

from fastapi import FastAPI

from obsidian_rag.v3_7.routes import agent, health

app = FastAPI(
    title="Obsidian RAG V3.7 Context Builder API",
    version="v3.7",
    description="Context Builder API that selects, orders, and formats current-run evidence before synthesis.",
)

app.include_router(health.router)
app.include_router(agent.router)
