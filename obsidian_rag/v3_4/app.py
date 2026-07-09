from __future__ import annotations

from fastapi import FastAPI

from obsidian_rag.v3_4.routes import health, planner

app = FastAPI(
    title="Obsidian RAG V3.4 Planner API",
    version="v3.4",
    description="Planner-only API that turns a question into structured plan JSON before retrieval execution.",
)

app.include_router(health.router)
app.include_router(planner.router)
