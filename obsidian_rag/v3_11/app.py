from fastapi import FastAPI

from obsidian_rag.v3_10.routes import runs
from obsidian_rag.v3_11.routes import agent, health, skills


app = FastAPI(
    title="Obsidian RAG V3.11 Skill System API",
    version="v3.11",
    description="Skill Registry、LLM Skill Router、按需加载和现有 Agentic RAG 的 JSON/SSE API。",
)

app.include_router(health.router)
app.include_router(skills.router)
app.include_router(agent.router)
app.include_router(runs.router)
