from __future__ import annotations

from fastapi import FastAPI

from obsidian_rag.v3_2.routes import agent, health

app = FastAPI(
    title="Obsidian RAG V3.2 Tool Calling API",
    version="v3.2",
    description="Agentic RAG API where the model selects search_notes, no_search, or clarify via tool calling.",
)

app.include_router(health.router)
app.include_router(agent.router)

