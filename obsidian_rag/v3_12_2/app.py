from fastapi import FastAPI

from obsidian_rag.console_api import create_console_router
from obsidian_rag.v3_10.routes import runs
from obsidian_rag.v3_12_2.routes import agent, health, rerank


app = FastAPI(
    title="Obsidian RAG V3.12.2 Retrieval Reranking API",
    version="v3.12.2",
    description="Dense/Keyword/RRF 后使用可插拔 CrossEncoder 重排，再构建 Parent Context。",
)

app.include_router(health.router)
app.include_router(agent.router)
app.include_router(rerank.router)
app.include_router(runs.router)
app.include_router(create_console_router("v3.12.2"))
