from fastapi import FastAPI

from obsidian_rag.v3_10.routes import runs
from obsidian_rag.v3_12_1.routes import agent, health, tools


app = FastAPI(
    title="Obsidian RAG V3.12.1 Agent Core Streaming API",
    version="v3.12.1",
    description="公共 Agent Core、统一 Tool Registry、JSON/SSE 和最终可见答案 answer_delta。",
)

app.include_router(health.router)
app.include_router(agent.router)
app.include_router(tools.router)
app.include_router(runs.router)
