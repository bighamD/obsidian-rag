from fastapi import FastAPI

from obsidian_rag.v3_9.routes import eval, health


app = FastAPI(
    title="Obsidian RAG V3.9 Agent Evaluation API",
    version="v3.9",
    description="JSON API for repeatable, trace-aware evaluation of the V3.8.1 integrated Agent.",
)

app.include_router(health.router)
app.include_router(eval.router)
