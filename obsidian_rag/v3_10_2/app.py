from fastapi import FastAPI

from obsidian_rag.v3_10.routes import runs
from obsidian_rag.v3_10_2.routes import agent, console, health


app = FastAPI(
    title="Obsidian RAG V3.10.2 Run Event Streaming API",
    version="v3.10.2",
    description="JSON and SSE APIs for streaming observable Agent Run events without exposing chain-of-thought.",
)

app.include_router(health.router)
app.include_router(agent.router)
app.include_router(runs.router)
app.include_router(console.router)

