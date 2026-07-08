from __future__ import annotations

from fastapi import FastAPI

from obsidian_rag.v3_3.routes import agent, health

app = FastAPI(
    title="Obsidian RAG V3.3 LangGraph API",
    version="v3.3",
    description="Agentic RAG API using LangGraph nodes for tool selection, retrieval, evidence check, and answer.",
)

app.include_router(health.router)
app.include_router(agent.router)

