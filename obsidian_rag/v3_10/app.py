from fastapi import FastAPI

from obsidian_rag.v3_10.routes import agent, health, runs


app = FastAPI(
    title="Obsidian RAG V3.10 Production Core API",
    version="v3.10",
    description="JSON API for V3.8.1 Agent runs with lifecycle, timing, tool summaries, token estimates, and standardized errors.",
)

app.include_router(health.router)
app.include_router(agent.router)
app.include_router(runs.router)
