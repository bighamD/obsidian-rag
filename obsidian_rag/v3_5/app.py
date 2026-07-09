from __future__ import annotations

from fastapi import FastAPI

from obsidian_rag.v3_5.routes import agent, health

app = FastAPI(
    title="Obsidian RAG V3.5 Planner Executor API",
    version="v3.5",
    description="Planner Executor API that plans, executes search steps, and synthesizes an answer with step results.",
)

app.include_router(health.router)
app.include_router(agent.router)
