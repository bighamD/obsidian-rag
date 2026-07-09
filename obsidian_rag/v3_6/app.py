from __future__ import annotations

from fastapi import FastAPI

from obsidian_rag.v3_6.routes import agent, health

app = FastAPI(
    title="Obsidian RAG V3.6 Evidence Checker API",
    version="v3.6",
    description="Evidence-checking planner executor API that retries search when planned evidence is missing.",
)

app.include_router(health.router)
app.include_router(agent.router)
