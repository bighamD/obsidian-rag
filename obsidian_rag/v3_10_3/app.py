from fastapi import FastAPI

from obsidian_rag.v3_10.routes import runs
from obsidian_rag.v3_10_2.routes import agent, console
from obsidian_rag.v3_10_3.routes import advanced, health


app = FastAPI(
    title="Obsidian RAG V3.10.3 LangGraph Advanced Patterns API",
    version="v3.10.3",
    description=(
        "Advanced LangGraph learning API with Subgraph, Send parallelism, Command routing, "
        "RetryPolicy, State History, messages stream, and the existing V3.10.2 JSON/SSE endpoints."
    ),
)

app.include_router(health.router)
app.include_router(advanced.router)
app.include_router(agent.router)
app.include_router(runs.router)
app.include_router(console.router)

