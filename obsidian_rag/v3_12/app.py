from fastapi import FastAPI

from obsidian_rag.v3_12.routes import health, mcp


app = FastAPI(
    title="Obsidian RAG V3.12 MCP Integration API",
    version="v3.12",
    description="学习 MCP Client/Server、tools/list、tools/call、Schema Adapter 和只读 RAG MCP Server。",
)

app.include_router(health.router)
app.include_router(mcp.router)
