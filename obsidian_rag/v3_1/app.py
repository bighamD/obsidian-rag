from __future__ import annotations

from fastapi import FastAPI

from obsidian_rag.v3_1.routes import agent, health

app = FastAPI(
    title="Obsidian RAG V3.1 LLM Router API",
    version="v3.1",
    description="Agentic RAG API with an LLM router that returns structured JSON decisions.",
)

app.include_router(health.router)
app.include_router(agent.router)

