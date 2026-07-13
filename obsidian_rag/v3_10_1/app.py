from fastapi import FastAPI

from obsidian_rag.v3_10.routes import agent, runs
from obsidian_rag.v3_10_1.routes import console, health


app = FastAPI(
    title="Obsidian RAG V3.10.1 Agent Console API",
    version="v3.10.1",
    description="JSON API for the Vite + Vue 3 Agent Console. It reuses V3.10 Production Run endpoints and adds console-oriented conversation reads.",
)

app.include_router(health.router)
app.include_router(agent.router)
app.include_router(runs.router)
app.include_router(console.router)
