from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from obsidian_rag.config import RagConfig
from obsidian_rag.config import load_config, resolve_ingest_path, with_collection
from obsidian_rag.pipeline import answer, ingest_path, search
from obsidian_rag.prompting import format_sources
from obsidian_rag.v1.schemas import SearchFilters, SearchMode
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v2.evaluation.dataset import load_eval_dataset
from obsidian_rag.v2.evaluation.retrieval import RetrievalEvaluator, default_retrieval_eval_output_path
from obsidian_rag.v3.agent.service import AgentService
from obsidian_rag.v3.schemas import AgentAskRequest
from obsidian_rag.v3_1.agent.service import AgentService as Agent31Service
from obsidian_rag.v3_1.router.service import RouterService
from obsidian_rag.v3_1.schemas import AgentAskRequest as Agent31AskRequest
from obsidian_rag.v3_2.agent.service import AgentService as Agent32Service
from obsidian_rag.v3_2.schemas import AgentAskRequest as Agent32AskRequest
from obsidian_rag.v3_3.agent.service import AgentService as Agent33Service
from obsidian_rag.v3_3.schemas import AgentAskRequest as Agent33AskRequest
from obsidian_rag.v3_4.planner.service import PlannerService
from obsidian_rag.v3_4.schemas import PlanRequest
from obsidian_rag.v3_5.agent.service import AgentService as Agent35Service
from obsidian_rag.v3_5.schemas import AgentAskRequest as Agent35AskRequest
from obsidian_rag.v3_6.agent.service import AgentService as Agent36Service
from obsidian_rag.v3_6.schemas import AgentAskRequest as Agent36AskRequest
from obsidian_rag.v3_7.agent.service import AgentService as Agent37Service
from obsidian_rag.v3_7.schemas import AgentAskRequest as Agent37AskRequest
from obsidian_rag.v3_8.agent.service import AgentService as Agent38Service
from obsidian_rag.v3_8.memory import SQLiteConversationMemoryStore, default_memory_db_path
from obsidian_rag.v3_8.schemas import AgentAskRequest as Agent38AskRequest
from obsidian_rag.v3_8_1.agent.service import AgentService as Agent381Service
from obsidian_rag.v3_8_1.compaction import ConversationCompactor as Conversation381Compactor
from obsidian_rag.v3_8_1.memory import SQLiteConversationMemoryStore as SQLite381ConversationMemoryStore
from obsidian_rag.v3_8_1.mysql_memory import MySQLConversationMemoryStore
from obsidian_rag.v3_8_1.schemas import AgentAskRequest as Agent381AskRequest
from obsidian_rag.v3_9.dependencies import default_agent_eval_memory_db_path
from obsidian_rag.v3_9.evaluation.dataset import load_agent_eval_dataset
from obsidian_rag.v3_9.evaluation.evaluator import AgentEvaluator, default_agent_eval_output_path
from obsidian_rag.v3_10.runtime.lifecycle import AgentRuntimeService
from obsidian_rag.v3_10.runtime.store import InMemoryRunStore
from obsidian_rag.v3_10.schemas import ProductionAskRequest
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v3_11.agent.service import SkillAgentService
from obsidian_rag.v3_11.schemas import SkillAskRequest
from obsidian_rag.v3_11.skills.registry import SkillRegistry
from obsidian_rag.v3_11_1.schemas import (
    DoclingIngestRequest,
    DoclingPathRequest,
    DoclingSearchRequest,
)
from obsidian_rag.v3_11_1.service import DoclingLearningService
from obsidian_rag.v3_11_2.schemas import FrameworkCompareRequest
from obsidian_rag.v3_11_2.service import FrameworkComparisonService
from obsidian_rag.v3_11_3.dependencies import get_registry_path
from obsidian_rag.v3_11_3.registry import KnowledgeBaseRegistry
from obsidian_rag.v3_11_3.router import CollectionRouter
from obsidian_rag.v3_11_3.schemas import CollectionRouteRequest, CollectionSearchRequest
from obsidian_rag.v3_11_3.service import CollectionRouterService
from obsidian_rag.v3_12.dependencies import get_mcp_service
from obsidian_rag.v3_12.schemas import McpCallRequest


def _add_production_ask_arguments(parser, memory_db_help: str) -> None:
    """为 V3.10 及其 Console 层复用同一套 Agent 运行参数。"""

    parser.add_argument("question")
    parser.add_argument("--conversation-id")
    parser.add_argument("--memory-window", type=int, default=3)
    parser.add_argument("--disable-memory-compaction", action="store_true")
    parser.add_argument("--memory-compaction-trigger-turns", type=int, default=4)
    parser.add_argument("--memory-compaction-trigger-tokens", type=int, default=3000)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    parser.add_argument("--max-steps", type=int, default=4)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--filter-path")
    parser.add_argument("--context-max-chunks", type=int, default=6)
    parser.add_argument("--context-token-budget", type=int, default=4000)
    parser.add_argument("--memory-db-path", type=Path, help=memory_db_help)


def main() -> None:
    parser = argparse.ArgumentParser(prog="obsidian-rag")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Index Markdown/PDF files into the local vector store")
    ingest_parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        help="Obsidian vault, folder, Markdown file, or PDF file. Defaults to RAG_VAULT_PATH.",
    )
    ingest_parser.add_argument("--recreate", action="store_true", help="Drop and rebuild the collection first")
    ingest_parser.add_argument("--collection", help="Target knowledge-base collection; defaults to RAG_COLLECTION")

    search_parser = subparsers.add_parser("search", help="Retrieve relevant chunks without calling the LLM")
    search_parser.add_argument("query")
    search_parser.add_argument("--top-k", type=int, default=5)
    search_parser.add_argument("--collection", help="Knowledge-base collection; defaults to RAG_COLLECTION")

    ask_parser = subparsers.add_parser("ask", help="Retrieve chunks and ask the configured LLM")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--top-k", type=int, default=5)
    ask_parser.add_argument("--collection", help="Knowledge-base collection; defaults to RAG_COLLECTION")

    eval_parser = subparsers.add_parser("eval", help="Run repeatable RAG evaluations")
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command", required=True)
    retrieval_eval_parser = eval_subparsers.add_parser("retrieval", help="Evaluate retrieval hit rate, MRR, and source recall")
    retrieval_eval_parser.add_argument("dataset", type=Path, help="YAML eval dataset path")
    retrieval_eval_parser.add_argument("--top-k", type=int, default=5)
    retrieval_eval_parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    retrieval_eval_parser.add_argument("--output", type=Path, help="Where to save the JSON report")
    retrieval_eval_parser.add_argument("--no-save", action="store_true", help="Print metrics without saving a JSON report")

    agent_parser = subparsers.add_parser("agent", help="Run lightweight agentic RAG")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command", required=True)
    agent_ask_parser = agent_subparsers.add_parser("ask", help="Let the agent decide whether and how to search")
    agent_ask_parser.add_argument("question")
    agent_ask_parser.add_argument("--top-k", type=int, default=5)
    agent_ask_parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent_ask_parser.add_argument("--max-steps", type=int, default=2)

    agent31_parser = subparsers.add_parser("agent-v3-1", help="Run V3.1 LLM-router agentic RAG")
    agent31_subparsers = agent31_parser.add_subparsers(dest="agent31_command", required=True)
    agent31_ask_parser = agent31_subparsers.add_parser("ask", help="Route with LLM JSON before deciding whether to search")
    agent31_ask_parser.add_argument("question")
    agent31_ask_parser.add_argument("--top-k", type=int, default=5)
    agent31_ask_parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent31_ask_parser.add_argument("--max-steps", type=int, default=1)

    agent32_parser = subparsers.add_parser("agent-v3-2", help="Run V3.2 tool-calling agentic RAG")
    agent32_subparsers = agent32_parser.add_subparsers(dest="agent32_command", required=True)
    agent32_ask_parser = agent32_subparsers.add_parser("ask", help="Let the model choose search_notes, no_search, or clarify")
    agent32_ask_parser.add_argument("question")
    agent32_ask_parser.add_argument("--top-k", type=int, default=5)
    agent32_ask_parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent32_ask_parser.add_argument("--max-steps", type=int, default=1)

    agent33_parser = subparsers.add_parser("agent-v3-3", help="Run V3.3 LangGraph agentic RAG")
    agent33_subparsers = agent33_parser.add_subparsers(dest="agent33_command", required=True)
    agent33_ask_parser = agent33_subparsers.add_parser("ask", help="Run the LangGraph node workflow")
    agent33_ask_parser.add_argument("question")
    agent33_ask_parser.add_argument("--top-k", type=int, default=5)
    agent33_ask_parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent33_ask_parser.add_argument("--max-steps", type=int, default=1)

    agent34_parser = subparsers.add_parser("agent-v3-4", help="Run V3.4 planner-only agent")
    agent34_subparsers = agent34_parser.add_subparsers(dest="agent34_command", required=True)
    agent34_plan_parser = agent34_subparsers.add_parser("plan", help="Generate structured plan JSON without executing retrieval")
    agent34_plan_parser.add_argument("question")
    agent34_plan_parser.add_argument("--top-k", type=int, default=5)
    agent34_plan_parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent34_plan_parser.add_argument("--max-steps", type=int, default=4)

    agent35_parser = subparsers.add_parser("agent-v3-5", help="Run V3.5 planner executor agentic RAG")
    agent35_subparsers = agent35_parser.add_subparsers(dest="agent35_command", required=True)
    agent35_ask_parser = agent35_subparsers.add_parser("ask", help="Plan, execute search steps, and synthesize an answer")
    agent35_ask_parser.add_argument("question")
    agent35_ask_parser.add_argument("--top-k", type=int, default=5)
    agent35_ask_parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent35_ask_parser.add_argument("--max-steps", type=int, default=4)

    agent36_parser = subparsers.add_parser("agent-v3-6", help="Run V3.6 evidence-checking planner executor agentic RAG")
    agent36_subparsers = agent36_parser.add_subparsers(dest="agent36_command", required=True)
    agent36_ask_parser = agent36_subparsers.add_parser("ask", help="Plan, execute, check evidence, retry search, and synthesize")
    agent36_ask_parser.add_argument("question")
    agent36_ask_parser.add_argument("--top-k", type=int, default=5)
    agent36_ask_parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent36_ask_parser.add_argument("--max-steps", type=int, default=4)
    agent36_ask_parser.add_argument("--max-retries", type=int, default=1)
    agent36_ask_parser.add_argument("--filter-path", help="Limit retrieval to a source path; useful for evidence-insufficient debugging")

    agent37_parser = subparsers.add_parser("agent-v3-7", help="Run V3.7 context-building agentic RAG")
    agent37_subparsers = agent37_parser.add_subparsers(dest="agent37_command", required=True)
    agent37_ask_parser = agent37_subparsers.add_parser("ask", help="Plan, execute, check evidence, build context, and synthesize")
    agent37_ask_parser.add_argument("question")
    agent37_ask_parser.add_argument("--top-k", type=int, default=5)
    agent37_ask_parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent37_ask_parser.add_argument("--max-steps", type=int, default=4)
    agent37_ask_parser.add_argument("--max-retries", type=int, default=1)
    agent37_ask_parser.add_argument("--filter-path", help="Limit retrieval to a source path")
    agent37_ask_parser.add_argument("--context-max-chunks", type=int, default=6)
    agent37_ask_parser.add_argument("--context-token-budget", type=int, default=4000)

    agent38_parser = subparsers.add_parser("agent-v3-8", help="Run V3.8 conversation-memory agentic RAG")
    agent38_subparsers = agent38_parser.add_subparsers(dest="agent38_command", required=True)
    agent38_ask_parser = agent38_subparsers.add_parser("ask", help="Load memory, run the agent, and persist the new turn")
    agent38_ask_parser.add_argument("question")
    agent38_ask_parser.add_argument("--conversation-id")
    agent38_ask_parser.add_argument("--memory-window", type=int, default=3)
    agent38_ask_parser.add_argument("--top-k", type=int, default=5)
    agent38_ask_parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent38_ask_parser.add_argument("--max-steps", type=int, default=4)
    agent38_ask_parser.add_argument("--max-retries", type=int, default=1)
    agent38_ask_parser.add_argument("--filter-path")
    agent38_ask_parser.add_argument("--context-max-chunks", type=int, default=6)
    agent38_ask_parser.add_argument("--context-token-budget", type=int, default=4000)
    agent38_ask_parser.add_argument("--memory-db-path", type=Path)

    agent381_parser = subparsers.add_parser("agent-v3-8-1", help="Run V3.8.1 conversation compaction agentic RAG")
    agent381_subparsers = agent381_parser.add_subparsers(dest="agent381_command", required=True)
    agent381_ask_parser = agent381_subparsers.add_parser(
        "ask",
        help="Load memory, compact old turns when needed, run the agent, and persist the new turn",
    )
    agent381_ask_parser.add_argument("question")
    agent381_ask_parser.add_argument("--conversation-id")
    agent381_ask_parser.add_argument("--memory-window", type=int, default=3)
    agent381_ask_parser.add_argument("--disable-memory-compaction", action="store_true")
    agent381_ask_parser.add_argument("--memory-compaction-trigger-turns", type=int, default=4)
    agent381_ask_parser.add_argument("--memory-compaction-trigger-tokens", type=int, default=3000)
    agent381_ask_parser.add_argument("--top-k", type=int, default=5)
    agent381_ask_parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent381_ask_parser.add_argument("--collection", help="检索目标 Collection；默认使用 RAG_COLLECTION")
    agent381_ask_parser.add_argument("--max-steps", type=int, default=4)
    agent381_ask_parser.add_argument("--max-retries", type=int, default=1)
    agent381_ask_parser.add_argument("--filter-path")
    agent381_ask_parser.add_argument("--context-max-chunks", type=int, default=6)
    agent381_ask_parser.add_argument("--context-token-budget", type=int, default=4000)
    agent381_ask_parser.add_argument("--memory-db-path", type=Path)
    agent381_compact_parser = agent381_subparsers.add_parser(
        "compact",
        help="Force or threshold-check conversation compaction without running RAG",
    )
    agent381_compact_parser.add_argument("conversation_id")
    agent381_compact_parser.add_argument("--keep-recent-turns", type=int, default=3)
    agent381_compact_parser.add_argument("--trigger-turns", type=int, default=4)
    agent381_compact_parser.add_argument("--trigger-tokens", type=int, default=3000)
    agent381_compact_parser.add_argument("--no-force", action="store_true")
    agent381_compact_parser.add_argument("--memory-db-path", type=Path)

    agent39_parser = subparsers.add_parser("agent-v3-9", help="Run V3.9 trace-aware Agent evaluation")
    agent39_subparsers = agent39_parser.add_subparsers(dest="agent39_command", required=True)
    agent39_eval_parser = agent39_subparsers.add_parser("eval", help="Evaluate V3.8.1 Agent behavior from a YAML case dataset")
    agent39_eval_parser.add_argument("dataset", type=Path, help="YAML agent evaluation dataset path")
    agent39_eval_parser.add_argument("--output", type=Path, help="Where to save the JSON evaluation report")
    agent39_eval_parser.add_argument("--no-save", action="store_true", help="Print the report summary without saving JSON")
    agent39_eval_parser.add_argument("--memory-db-path", type=Path, help="Isolated SQLite path used by evaluation Agent runs")

    agent310_parser = subparsers.add_parser("agent-v3-10", help="Run V3.10 Production Core with lifecycle observation")
    agent310_subparsers = agent310_parser.add_subparsers(dest="agent310_command", required=True)
    agent310_ask_parser = agent310_subparsers.add_parser("ask", help="Run V3.8.1 Agent and print the V3.10 run summary")
    _add_production_ask_arguments(agent310_ask_parser, "V3.10 SQLite Memory DB path")

    agent3101_parser = subparsers.add_parser("agent-v3-10-1", help="Run the V3.10.1 Agent Console JSON flow")
    agent3101_subparsers = agent3101_parser.add_subparsers(dest="agent3101_command", required=True)
    agent3101_ask_parser = agent3101_subparsers.add_parser("ask", help="Run the Console-backed JSON Agent request from CLI")
    _add_production_ask_arguments(agent3101_ask_parser, "V3.10.1 Console SQLite Memory DB path")

    agent3102_parser = subparsers.add_parser("agent-v3-10-2", help="Stream V3.10.2 Agent events over SSE")
    agent3102_subparsers = agent3102_parser.add_subparsers(dest="agent3102_command", required=True)
    agent3102_ask_parser = agent3102_subparsers.add_parser("ask", help="Call the V3.10.2 SSE endpoint and print events")
    _add_production_ask_arguments(agent3102_ask_parser, "V3.10.2 SSE SQLite Memory DB path")
    agent3102_ask_parser.add_argument("--api-base", default="http://127.0.0.1:8014", help="V3.10.2 API base URL")

    agent311_parser = subparsers.add_parser("agent-v3-11", help="Run V3.11 Skill System Agent")
    agent311_subparsers = agent311_parser.add_subparsers(dest="agent311_command", required=True)
    agent311_ask_parser = agent311_subparsers.add_parser(
        "ask",
        help="Discover Skills, route with LLM, lazy-load the selected SKILL.md, and run Agentic RAG",
    )
    _add_production_ask_arguments(agent311_ask_parser, "V3.11 Skill System MySQL Memory DB path")
    agent311_ask_parser.add_argument("--skill-name", help="Force one Skill for deterministic debugging")
    agent311_ask_parser.add_argument("--collection", help="检索目标 Collection；默认使用 RAG_COLLECTION")
    agent311_ask_parser.add_argument("--disable-skill-router", action="store_true")
    agent311_ask_parser.add_argument("--skill-root", type=Path, default=Path("skills"))
    agent311_skills_parser = agent311_subparsers.add_parser("skills", help="Inspect local Skill Registry")
    agent311_skills_subparsers = agent311_skills_parser.add_subparsers(
        dest="agent311_skills_command",
        required=True,
    )
    agent311_list_parser = agent311_skills_subparsers.add_parser("list", help="List discovered Skill manifests")
    agent311_list_parser.add_argument("--skill-root", type=Path, default=Path("skills"))

    documents3111_parser = subparsers.add_parser(
        "documents-v3-11-1",
        help="Learn Docling conversion, HybridChunker and shared structured ingest",
    )
    documents3111_subparsers = documents3111_parser.add_subparsers(
        dest="documents3111_command",
        required=True,
    )
    documents3111_convert = documents3111_subparsers.add_parser("convert", help="Convert one file to DoclingDocument")
    documents3111_convert.add_argument("path", type=Path, nargs="?")
    documents3111_chunks = documents3111_subparsers.add_parser("chunks", help="Preview Docling HybridChunker output")
    documents3111_chunks.add_argument("path", type=Path, nargs="?")
    documents3111_ingest = documents3111_subparsers.add_parser("ingest", help="Rebuild shared Qdrant with Docling chunks")
    documents3111_ingest.add_argument("path", type=Path, nargs="?")
    documents3111_ingest.add_argument("--recreate", action="store_true")
    documents3111_ingest.add_argument("--collection", help="写入目标 Collection；默认使用 RAG_COLLECTION")
    documents3111_search = documents3111_subparsers.add_parser("search", help="Search the shared Docling index")
    documents3111_search.add_argument("query")
    documents3111_search.add_argument("--top-k", type=int, default=5)
    documents3111_search.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    documents3111_search.add_argument("--collection", help="检索目标 Collection；默认使用 RAG_COLLECTION")

    chunking3112_parser = subparsers.add_parser(
        "chunking-v3-11-2",
        help="Compare LangChain and LlamaIndex chunking/retrieval strategies",
    )
    chunking3112_subparsers = chunking3112_parser.add_subparsers(dest="chunking3112_command", required=True)
    chunking3112_compare = chunking3112_subparsers.add_parser("compare", help="Run all three request-scoped strategies")
    chunking3112_compare.add_argument("query")
    chunking3112_compare.add_argument("--path", type=Path)
    chunking3112_compare.add_argument("--top-k", type=int, default=4)
    chunking3112_compare.add_argument("--langchain-parent-chars", type=int, default=2000)
    chunking3112_compare.add_argument("--langchain-child-chars", type=int, default=400)
    chunking3112_compare.add_argument("--llama-parent-tokens", type=int, default=1024)
    chunking3112_compare.add_argument("--llama-child-tokens", type=int, default=256)
    chunking3112_compare.add_argument("--semantic-breakpoint-percentile", type=int, default=95)

    collections3113_parser = subparsers.add_parser(
        "collections-v3-11-3",
        help="Route questions to one or more knowledge-base collections and run cross-collection retrieval",
    )
    collections3113_subparsers = collections3113_parser.add_subparsers(
        dest="collections3113_command",
        required=True,
    )
    collections3113_list = collections3113_subparsers.add_parser("list", help="List Knowledge Base Registry entries")
    collections3113_list.add_argument("--registry", type=Path)
    collections3113_route = collections3113_subparsers.add_parser("route", help="Run Collection Router only")
    collections3113_route.add_argument("question")
    collections3113_route.add_argument("--collection")
    collections3113_route.add_argument("--disable-router", action="store_true")
    collections3113_route.add_argument("--max-collections", type=int, default=2)
    collections3113_route.add_argument("--registry", type=Path)
    collections3113_search = collections3113_subparsers.add_parser("search", help="Route and search selected collections")
    collections3113_search.add_argument("question")
    collections3113_search.add_argument("--collection")
    collections3113_search.add_argument("--disable-router", action="store_true")
    collections3113_search.add_argument("--max-collections", type=int, default=2)
    collections3113_search.add_argument("--top-k", type=int, default=5)
    collections3113_search.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    collections3113_search.add_argument("--registry", type=Path)

    mcp312_parser = subparsers.add_parser("mcp-v3-12", help="Learn MCP Client/Server and explicit Tool calls")
    mcp312_subparsers = mcp312_parser.add_subparsers(dest="mcp312_command", required=True)
    mcp312_subparsers.add_parser("servers", help="List configured stdio MCP Servers")
    mcp312_tools = mcp312_subparsers.add_parser("tools", help="Run tools/list against one or all MCP Servers")
    mcp312_tools.add_argument("--server", dest="server_name")
    mcp312_call = mcp312_subparsers.add_parser("call", help="Run tools/call against one MCP Server")
    mcp312_call.add_argument("server_name")
    mcp312_call.add_argument("tool_name")
    mcp312_call.add_argument("--arguments", default="{}", help="JSON object passed to the MCP Tool")
    mcp312_subparsers.add_parser("serve-demo", help="Run the low-risk demo MCP Server over stdio")
    mcp312_subparsers.add_parser("serve-rag", help="Expose local RAG read-only tools over stdio")

    agent3121_parser = subparsers.add_parser(
        "agent-v3-12-1",
        help="Run the public Agent Core JSON or visible-answer SSE endpoint",
    )
    agent3121_subparsers = agent3121_parser.add_subparsers(dest="agent3121_command", required=True)
    agent3121_ask = agent3121_subparsers.add_parser("ask", help="Call V3.12.1 Agent Core")
    _add_production_ask_arguments(agent3121_ask, "已迁移到 MySQL，此参数仅为旧 CLI 兼容保留")
    agent3121_ask.add_argument("--collection", help="本次检索使用的知识库 collection")
    agent3121_ask.add_argument("--json", action="store_true", help="使用同步 JSON 而不是 answer_delta SSE")
    agent3121_ask.add_argument("--api-base", default="http://127.0.0.1:8020")

    agent3122_parser = subparsers.add_parser(
        "agent-v3-12-2",
        help="Run V3.12.2 Agent Core with retrieval reranking",
    )
    agent3122_subparsers = agent3122_parser.add_subparsers(dest="agent3122_command", required=True)
    agent3122_ask = agent3122_subparsers.add_parser("ask", help="Call V3.12.2 JSON or answer_delta SSE")
    _add_production_ask_arguments(agent3122_ask, "已迁移到 MySQL，此参数仅为旧 CLI 兼容保留")
    agent3122_ask.add_argument("--collection", help="本次检索使用的知识库 collection")
    agent3122_ask.add_argument("--json", action="store_true", help="使用同步 JSON 而不是 SSE")
    agent3122_ask.add_argument("--api-base", default="http://127.0.0.1:8020")
    agent3122_rerank = agent3122_subparsers.add_parser("rerank", help="Inspect retrieval rank vs rerank rank")
    agent3122_rerank.add_argument("query")
    agent3122_rerank.add_argument("--collection")
    agent3122_rerank.add_argument("--collections", nargs="*", default=[])
    agent3122_rerank.add_argument("--top-k", type=int, default=5)
    agent3122_rerank.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent3122_rerank.add_argument("--api-base", default="http://127.0.0.1:8020")

    agent3123_parser = subparsers.add_parser(
        "agent-v3-12-3",
        help="Run the production-style MCP Agent integration",
    )
    agent3123_subparsers = agent3123_parser.add_subparsers(dest="agent3123_command", required=True)
    agent3123_ask = agent3123_subparsers.add_parser("ask", help="Run JSON or SSE with automatic MCP Tool selection")
    _add_production_ask_arguments(agent3123_ask, "已迁移到 MySQL，此参数仅为旧 CLI 兼容保留")
    agent3123_ask.add_argument("--collection", help="本次检索使用的知识库 collection")
    agent3123_ask.add_argument("--disable-mcp", action="store_true", help="本次请求不向 Planner 暴露 MCP Tools")
    agent3123_ask.add_argument("--mcp-tool-name", action="append", dest="mcp_tool_names")
    agent3123_ask.add_argument("--json", action="store_true", help="使用同步 JSON 而不是 SSE")
    agent3123_ask.add_argument("--api-base", default="http://127.0.0.1:8020")
    agent3123_mcp_status = agent3123_subparsers.add_parser("mcp-status", help="Read persistent MCP runtime status")
    agent3123_mcp_status.add_argument("--api-base", default="http://127.0.0.1:8020")
    agent3123_mcp_refresh = agent3123_subparsers.add_parser("mcp-refresh", help="Refresh or reconnect MCP Servers")
    agent3123_mcp_refresh.add_argument("--server")
    agent3123_mcp_refresh.add_argument("--reconnect", action="store_true")
    agent3123_mcp_refresh.add_argument("--api-base", default="http://127.0.0.1:8020")
    agent3123_mcp_call = agent3123_subparsers.add_parser("mcp-call", help="Explicitly call one persistent MCP Tool")
    agent3123_mcp_call.add_argument("name")
    agent3123_mcp_call.add_argument("--arguments", default="{}")
    agent3123_mcp_call.add_argument("--api-base", default="http://127.0.0.1:8020")

    agent3124_parser = subparsers.add_parser(
        "agent-v3-12-4",
        help="Run unified Collection Routing, Reranking and MCP Agent",
    )
    agent3124_subparsers = agent3124_parser.add_subparsers(dest="agent3124_command", required=True)
    agent3124_ask = agent3124_subparsers.add_parser("ask", help="Run JSON or SSE with automatic Collection routing")
    _add_production_ask_arguments(agent3124_ask, "已迁移到 MySQL，此参数仅为旧 CLI 兼容保留")
    agent3124_ask.add_argument("--collection", help="显式 Collection；为空时自动路由")
    agent3124_ask.add_argument("--disable-collection-router", action="store_true")
    agent3124_ask.add_argument("--max-collections", type=int, default=2, choices=[1, 2, 3])
    agent3124_ask.add_argument("--disable-mcp", action="store_true")
    agent3124_ask.add_argument("--mcp-tool-name", action="append", dest="mcp_tool_names")
    agent3124_ask.add_argument("--json", action="store_true")
    agent3124_ask.add_argument("--api-base", default="http://127.0.0.1:8020")
    agent3124_collections = agent3124_subparsers.add_parser("collections", help="Read Knowledge Base Registry")
    agent3124_collections.add_argument("--api-base", default="http://127.0.0.1:8020")
    agent3124_route = agent3124_subparsers.add_parser("route", help="Debug Collection Router without retrieval")
    agent3124_route.add_argument("question")
    agent3124_route.add_argument("--collection")
    agent3124_route.add_argument("--disable-collection-router", action="store_true")
    agent3124_route.add_argument("--max-collections", type=int, default=2, choices=[1, 2, 3])
    agent3124_route.add_argument("--api-base", default="http://127.0.0.1:8020")

    agent313_parser = subparsers.add_parser(
        "agent-v3-13",
        help="Run V3.13 Permission Policy over the V3.12.4 Agent",
    )
    agent313_subparsers = agent313_parser.add_subparsers(dest="agent313_command", required=True)
    agent313_ask = agent313_subparsers.add_parser("ask", help="Run the permission-aware Agent JSON or SSE")
    _add_production_ask_arguments(agent313_ask, "已迁移到 MySQL，此参数仅为旧 CLI 兼容保留")
    agent313_ask.add_argument("--collection", help="显式 Collection；为空时自动路由")
    agent313_ask.add_argument("--disable-collection-router", action="store_true")
    agent313_ask.add_argument("--max-collections", type=int, default=2, choices=[1, 2, 3])
    agent313_ask.add_argument("--disable-mcp", action="store_true")
    agent313_ask.add_argument("--mcp-tool-name", action="append", dest="mcp_tool_names")
    agent313_ask.add_argument(
        "--principal-profile",
        choices=["standard", "knowledge-only", "restricted"],
        default="standard",
    )
    agent313_ask.add_argument("--json", action="store_true")
    agent313_ask.add_argument("--api-base", default="http://127.0.0.1:8022")
    agent313_policy = agent313_subparsers.add_parser("policy", help="Evaluate one Tool without executing it")
    agent313_policy.add_argument("tool_name")
    agent313_policy.add_argument("--arguments", default="{}")
    agent313_policy.add_argument(
        "--principal-profile",
        choices=["standard", "knowledge-only", "restricted", "writer"],
        default="standard",
    )
    agent313_policy.add_argument("--api-base", default="http://127.0.0.1:8022")
    agent313_audit = agent313_subparsers.add_parser("audit", help="Read recent in-memory permission audit records")
    agent313_audit.add_argument("--limit", type=int, default=20)
    agent313_audit.add_argument("--api-base", default="http://127.0.0.1:8022")

    agent314_parser = subparsers.add_parser(
        "agent-v3-14",
        help="Run V3.14 Docker Sandbox Agent and explicit Sandbox tools",
    )
    agent314_subparsers = agent314_parser.add_subparsers(dest="agent314_command", required=True)
    agent314_ask = agent314_subparsers.add_parser("ask", help="Run the Sandbox-aware Agent JSON or SSE")
    _add_production_ask_arguments(agent314_ask, "已迁移到 MySQL，此参数仅为旧 CLI 兼容保留")
    agent314_ask.add_argument("--collection")
    agent314_ask.add_argument("--disable-collection-router", action="store_true")
    agent314_ask.add_argument("--max-collections", type=int, default=2, choices=[1, 2, 3])
    agent314_ask.add_argument("--disable-mcp", action="store_true")
    agent314_ask.add_argument("--mcp-tool-name", action="append", dest="mcp_tool_names")
    agent314_ask.add_argument("--disable-sandbox", action="store_true")
    agent314_ask.add_argument("--disable-skill-router", action="store_true")
    agent314_ask.add_argument("--skill-name")
    agent314_ask.add_argument(
        "--principal-profile",
        choices=["standard", "knowledge-only", "restricted", "sandbox"],
        default="standard",
    )
    agent314_ask.add_argument("--json", action="store_true")
    agent314_ask.add_argument("--api-base", default="http://127.0.0.1:8023")
    agent314_sandbox = agent314_subparsers.add_parser("sandbox", help="Call one Sandbox Tool through Policy")
    agent314_sandbox.add_argument("tool_name", choices=["read_file", "write_file", "list_files", "run_command"])
    agent314_sandbox.add_argument("--run-id", default="sandbox_cli_debug")
    agent314_sandbox.add_argument("--arguments", default="{}")
    agent314_sandbox.add_argument("--principal-profile", choices=["standard", "restricted", "sandbox"], default="sandbox")
    agent314_sandbox.add_argument("--api-base", default="http://127.0.0.1:8023")

    agent315_parser = subparsers.add_parser(
        "agent-v3-15",
        help="Run V3.15 persistent checkpoint and HITL approval flow",
    )
    agent315_subparsers = agent315_parser.add_subparsers(dest="agent315_command", required=True)
    agent315_ask = agent315_subparsers.add_parser("ask", help="Start a recoverable Agent Run")
    _add_production_ask_arguments(agent315_ask, "已迁移到 MySQL，此参数仅为旧 CLI 兼容保留")
    agent315_ask.add_argument("--collection")
    agent315_ask.add_argument("--disable-collection-router", action="store_true")
    agent315_ask.add_argument("--max-collections", type=int, default=2, choices=[1, 2, 3])
    agent315_ask.add_argument("--disable-mcp", action="store_true")
    agent315_ask.add_argument("--mcp-tool-name", action="append", dest="mcp_tool_names")
    agent315_ask.add_argument("--disable-sandbox", action="store_true")
    agent315_ask.add_argument("--disable-skill-router", action="store_true")
    agent315_ask.add_argument("--skill-name")
    agent315_ask.add_argument(
        "--principal-profile",
        choices=["standard", "knowledge-only", "restricted", "sandbox"],
        default="sandbox",
    )
    agent315_ask.add_argument("--json", action="store_true")
    agent315_ask.add_argument("--api-base", default="http://127.0.0.1:8024")
    agent315_resume = agent315_subparsers.add_parser("resume", help="Resume a waiting Run")
    agent315_resume.add_argument("run_id")
    agent315_resume.add_argument("--action", choices=["allow", "deny", "edit"], required=True)
    agent315_resume.add_argument("--step-arguments", default="{}", help="edit 时使用的 step_id -> arguments JSON object")
    agent315_resume.add_argument("--comment")
    agent315_resume.add_argument("--api-base", default="http://127.0.0.1:8024")
    agent315_recover = agent315_subparsers.add_parser("recover", help="Retry a failed Run from its latest checkpoint")
    agent315_recover.add_argument("run_id")
    agent315_recover.add_argument("--api-base", default="http://127.0.0.1:8024")

    agent316_parser = subparsers.add_parser(
        "agent-v3-16",
        help="Run V3.16 DeepAgents Tool Loop, HITL and Artifact flow",
    )
    agent316_subparsers = agent316_parser.add_subparsers(dest="agent316_command", required=True)
    agent316_ask = agent316_subparsers.add_parser("ask", help="Start a Deep Agent JSON or SSE Run")
    agent316_ask.add_argument("question")
    agent316_ask.add_argument("--conversation-id")
    agent316_ask.add_argument("--collection")
    agent316_ask.add_argument("--top-k", type=int, default=5)
    agent316_ask.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent316_ask.add_argument("--filter-path")
    agent316_ask.add_argument("--max-iterations", type=int, default=12)
    agent316_ask.add_argument("--json", action="store_true")
    agent316_ask.add_argument("--api-base", default="http://127.0.0.1:8025")
    agent316_resume = agent316_subparsers.add_parser("resume", help="Resume a Deep Agent write approval")
    agent316_resume.add_argument("run_id")
    agent316_resume.add_argument("--action", choices=["allow", "deny", "edit"], required=True)
    agent316_resume.add_argument("--step-arguments", default="{}")
    agent316_resume.add_argument("--comment")
    agent316_resume.add_argument("--api-base", default="http://127.0.0.1:8025")
    agent316_inspect = agent316_subparsers.add_parser("inspect", help="Read one persisted Deep Agent Run")
    agent316_inspect.add_argument("run_id")
    agent316_inspect.add_argument("--api-base", default="http://127.0.0.1:8025")

    agent317_parser = subparsers.add_parser(
        "agent-v3-17",
        help="Run V3.17 durable Thread, long-term Memory and Context flow",
    )
    agent317_subparsers = agent317_parser.add_subparsers(dest="agent317_command", required=True)
    agent317_ask = agent317_subparsers.add_parser("ask", help="Start or continue a durable Conversation")
    agent317_ask.add_argument("question")
    agent317_ask.add_argument("--conversation-id")
    agent317_ask.add_argument("--tenant-id", default="tenant_demo")
    agent317_ask.add_argument("--user-id", default="user_demo")
    agent317_ask.add_argument("--assistant-id", default="obsidian_rag")
    agent317_ask.add_argument("--collection")
    agent317_ask.add_argument("--top-k", type=int, default=5)
    agent317_ask.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    agent317_ask.add_argument("--max-iterations", type=int, default=12)
    agent317_ask.add_argument("--json", action="store_true")
    agent317_ask.add_argument("--api-base", default="http://127.0.0.1:8026")
    agent317_resume = agent317_subparsers.add_parser("resume", help="Resume a V3.17 Artifact approval")
    agent317_resume.add_argument("run_id")
    agent317_resume.add_argument("--action", choices=["allow", "deny", "edit"], required=True)
    agent317_resume.add_argument("--step-arguments", default="{}")
    agent317_resume.add_argument("--comment")
    agent317_resume.add_argument("--api-base", default="http://127.0.0.1:8026")
    agent317_recover = agent317_subparsers.add_parser(
        "recover",
        help="Retry a failed V3.17 Run from its stable Thread checkpoint",
    )
    agent317_recover.add_argument("run_id")
    agent317_recover.add_argument("--api-base", default="http://127.0.0.1:8026")
    agent317_inspect = agent317_subparsers.add_parser("inspect", help="Read one persisted V3.17 Run")
    agent317_inspect.add_argument("run_id")
    agent317_inspect.add_argument("--api-base", default="http://127.0.0.1:8026")
    agent317_memory = agent317_subparsers.add_parser("memory", help="List, put or delete long-term Memory")
    agent317_memory.add_argument("action", choices=["list", "put", "delete"])
    agent317_memory.add_argument("--memory-id")
    agent317_memory.add_argument("--kind", choices=["preference", "fact", "decision"], default="preference")
    agent317_memory.add_argument("--content")
    agent317_memory.add_argument("--tenant-id", default="tenant_demo")
    agent317_memory.add_argument("--user-id", default="user_demo")
    agent317_memory.add_argument("--assistant-id", default="obsidian_rag")
    agent317_memory.add_argument("--api-base", default="http://127.0.0.1:8026")

    agent3103_parser = subparsers.add_parser("agent-v3-10-3", help="Run V3.10.3 LangGraph Advanced Patterns")
    agent3103_subparsers = agent3103_parser.add_subparsers(dest="agent3103_command", required=True)
    agent3103_ask_parser = agent3103_subparsers.add_parser("ask", help="Call the Advanced Graph JSON or SSE endpoint")
    _add_production_ask_arguments(agent3103_ask_parser, "已迁移到 MySQL，此参数仅为旧 CLI 兼容保留")
    agent3103_ask_parser.add_argument("--thread-id", help="LangGraph Checkpointer thread_id")
    agent3103_ask_parser.add_argument("--max-parallel-searches", type=int, default=4)
    agent3103_ask_parser.add_argument("--simulate-transient-search-failure", action="store_true")
    agent3103_ask_parser.add_argument("--json", action="store_true", help="使用同步 JSON 接口而不是 SSE")
    agent3103_ask_parser.add_argument("--api-base", default="http://127.0.0.1:8015")
    agent3103_history_parser = agent3103_subparsers.add_parser("history", help="Read LangGraph State History")
    agent3103_history_parser.add_argument("thread_id")
    agent3103_history_parser.add_argument("--limit", type=int, default=20)
    agent3103_history_parser.add_argument("--api-base", default="http://127.0.0.1:8015")

    args = parser.parse_args()
    config = load_config()

    if args.command == "ingest":
        request_config = with_collection(config, args.collection)
        path = resolve_ingest_path(args.path, request_config)
        document_count, chunk_count = ingest_path(path, config=request_config, recreate=args.recreate)
        print(f"Indexed {document_count} documents into {chunk_count} chunks in {request_config.collection_name}.")
        return

    if args.command == "search":
        request_config = with_collection(config, args.collection)
        results = search(args.query, config=request_config, top_k=args.top_k)
        print(f"Collection: {request_config.collection_name}")
        _print_results(results)
        return

    if args.command == "ask":
        request_config = with_collection(config, args.collection)
        response, results = answer(args.question, config=request_config, top_k=args.top_k)
        print(f"Collection: {request_config.collection_name}")
        print(response.strip())
        _print_sources(format_sources(results))
        return

    if args.command == "eval" and args.eval_command == "retrieval":
        output_path = None if args.no_save else args.output or default_retrieval_eval_output_path()
        run_retrieval_eval(
            dataset_path=args.dataset,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            output_path=output_path,
        )
        return

    if args.command == "agent" and args.agent_command == "ask":
        run_agent_ask(
            question=args.question,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
        )
        return

    if args.command == "agent-v3-1" and args.agent31_command == "ask":
        run_agent31_ask(
            question=args.question,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
        )
        return

    if args.command == "agent-v3-2" and args.agent32_command == "ask":
        run_agent32_ask(
            question=args.question,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
        )
        return

    if args.command == "agent-v3-3" and args.agent33_command == "ask":
        run_agent33_ask(
            question=args.question,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
        )
        return

    if args.command == "agent-v3-4" and args.agent34_command == "plan":
        run_agent34_plan(
            question=args.question,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
        )
        return

    if args.command == "agent-v3-5" and args.agent35_command == "ask":
        run_agent35_ask(
            question=args.question,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
        )
        return

    if args.command == "agent-v3-6" and args.agent36_command == "ask":
        run_agent36_ask(
            question=args.question,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
        )
        return

    if args.command == "agent-v3-7" and args.agent37_command == "ask":
        run_agent37_ask(
            question=args.question,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
        )
        return

    if args.command == "agent-v3-8" and args.agent38_command == "ask":
        run_agent38_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            collection=args.collection,
            memory_window=args.memory_window,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            memory_db_path=args.memory_db_path,
        )
        return

    if args.command == "agent-v3-8-1" and args.agent381_command == "ask":
        run_agent381_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            memory_db_path=args.memory_db_path,
            collection=args.collection,
        )
        return

    if args.command == "agent-v3-8-1" and args.agent381_command == "compact":
        run_agent381_compact(
            conversation_id=args.conversation_id,
            config=config,
            keep_recent_turns=args.keep_recent_turns,
            trigger_turns=args.trigger_turns,
            trigger_tokens=args.trigger_tokens,
            force=not args.no_force,
            memory_db_path=args.memory_db_path,
        )
        return

    if args.command == "agent-v3-9" and args.agent39_command == "eval":
        output_path = None if args.no_save else args.output or default_agent_eval_output_path()
        run_agent39_eval(
            dataset_path=args.dataset,
            config=config,
            output_path=output_path,
            memory_db_path=args.memory_db_path,
        )
        return

    if args.command == "agent-v3-10" and args.agent310_command == "ask":
        run_agent310_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            memory_db_path=args.memory_db_path,
        )
        return

    if args.command == "agent-v3-10-1" and args.agent3101_command == "ask":
        run_agent3101_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            memory_db_path=args.memory_db_path,
        )
        return

    if args.command == "agent-v3-10-2" and args.agent3102_command == "ask":
        run_agent3102_stream(
            question=args.question,
            conversation_id=args.conversation_id,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            config=config,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            api_base=args.api_base,
        )
        return

    if args.command == "agent-v3-11" and args.agent311_command == "ask":
        run_agent311_ask(
            question=args.question,
            config=config,
            conversation_id=args.conversation_id,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            collection=args.collection,
            skill_name=args.skill_name,
            skill_router_enabled=not args.disable_skill_router,
            skill_root=args.skill_root,
        )
        return

    if args.command == "agent-v3-11" and args.agent311_command == "skills" and args.agent311_skills_command == "list":
        run_agent311_list(args.skill_root)
        return

    if args.command == "documents-v3-11-1":
        run_documents3111(
            command=args.documents3111_command,
            config=config,
            path=getattr(args, "path", None),
            recreate=getattr(args, "recreate", False),
            query=getattr(args, "query", None),
            top_k=getattr(args, "top_k", 5),
            mode=getattr(args, "mode", "hybrid"),
            collection=getattr(args, "collection", None),
        )
        return

    if args.command == "chunking-v3-11-2" and args.chunking3112_command == "compare":
        run_chunking3112_compare(
            config=config,
            query=args.query,
            path=args.path,
            top_k=args.top_k,
            langchain_parent_chars=args.langchain_parent_chars,
            langchain_child_chars=args.langchain_child_chars,
            llama_parent_tokens=args.llama_parent_tokens,
            llama_child_tokens=args.llama_child_tokens,
            semantic_breakpoint_percentile=args.semantic_breakpoint_percentile,
        )
        return

    if args.command == "collections-v3-11-3":
        run_collections3113(
            command=args.collections3113_command,
            config=config,
            question=getattr(args, "question", None),
            collection=getattr(args, "collection", None),
            router_enabled=not getattr(args, "disable_router", False),
            max_collections=getattr(args, "max_collections", 2),
            top_k=getattr(args, "top_k", 5),
            mode=getattr(args, "mode", "hybrid"),
            registry_path=getattr(args, "registry", None),
        )
        return

    if args.command == "mcp-v3-12":
        run_mcp312(
            command=args.mcp312_command,
            server_name=getattr(args, "server_name", None),
            tool_name=getattr(args, "tool_name", None),
            arguments_json=getattr(args, "arguments", "{}"),
        )
        return

    if args.command == "agent-v3-12-1" and args.agent3121_command == "ask":
        run_agent3121_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            collection=args.collection,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            api_base=args.api_base,
            stream=not args.json,
        )
        return

    if args.command == "agent-v3-12-2" and args.agent3122_command == "ask":
        run_agent3121_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            collection=args.collection,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            api_base=args.api_base,
            stream=not args.json,
        )
        return

    if args.command == "agent-v3-12-2" and args.agent3122_command == "rerank":
        run_agent3122_rerank(
            query=args.query,
            collection=args.collection,
            collections=args.collections,
            top_k=args.top_k,
            mode=args.mode,
            api_base=args.api_base,
        )
        return

    if args.command == "agent-v3-12-3" and args.agent3123_command == "ask":
        run_agent3121_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            collection=args.collection,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            api_base=args.api_base,
            stream=not args.json,
            mcp_enabled=not args.disable_mcp,
            mcp_tool_names=args.mcp_tool_names,
        )
        return

    if args.command == "agent-v3-12-3":
        run_agent3123_mcp(
            command=args.agent3123_command,
            api_base=args.api_base,
            server_name=getattr(args, "server", None),
            reconnect=getattr(args, "reconnect", False),
            tool_name=getattr(args, "name", None),
            arguments_json=getattr(args, "arguments", "{}"),
        )
        return

    if args.command == "agent-v3-12-4" and args.agent3124_command == "ask":
        run_agent3121_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            collection=args.collection,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            api_base=args.api_base,
            stream=not args.json,
            mcp_enabled=not args.disable_mcp,
            mcp_tool_names=args.mcp_tool_names,
            collection_router_enabled=not args.disable_collection_router,
            max_collections=args.max_collections,
        )
        return

    if args.command == "agent-v3-12-4":
        run_agent3124_collections(
            command=args.agent3124_command,
            api_base=args.api_base,
            question=getattr(args, "question", None),
            collection=getattr(args, "collection", None),
            router_enabled=not getattr(args, "disable_collection_router", False),
            max_collections=getattr(args, "max_collections", 2),
        )
        return

    if args.command == "agent-v3-13" and args.agent313_command == "ask":
        run_agent3121_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            collection=args.collection,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            api_base=args.api_base,
            stream=not args.json,
            mcp_enabled=not args.disable_mcp,
            mcp_tool_names=args.mcp_tool_names,
            collection_router_enabled=not args.disable_collection_router,
            max_collections=args.max_collections,
            principal=_permission_principal(args.principal_profile),
        )
        return

    if args.command == "agent-v3-13":
        run_agent313_permission(
            command=args.agent313_command,
            api_base=args.api_base,
            tool_name=getattr(args, "tool_name", None),
            arguments_json=getattr(args, "arguments", "{}"),
            principal_profile=getattr(args, "principal_profile", "standard"),
            limit=getattr(args, "limit", 20),
        )
        return

    if args.command == "agent-v3-14" and args.agent314_command == "ask":
        run_agent3121_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            collection=args.collection,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            api_base=args.api_base,
            stream=not args.json,
            mcp_enabled=not args.disable_mcp,
            mcp_tool_names=args.mcp_tool_names,
            collection_router_enabled=not args.disable_collection_router,
            max_collections=args.max_collections,
            principal=_permission_principal(args.principal_profile),
            sandbox_enabled=not args.disable_sandbox,
            skill_router_enabled=not args.disable_skill_router,
            skill_name=args.skill_name,
        )
        return

    if args.command == "agent-v3-14":
        run_agent314_sandbox(
            api_base=args.api_base,
            tool_name=args.tool_name,
            run_id=args.run_id,
            arguments_json=args.arguments,
            principal_profile=args.principal_profile,
        )
        return

    if args.command == "agent-v3-15" and args.agent315_command == "ask":
        run_agent3121_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            collection=args.collection,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            api_base=args.api_base,
            stream=not args.json,
            mcp_enabled=not args.disable_mcp,
            mcp_tool_names=args.mcp_tool_names,
            collection_router_enabled=not args.disable_collection_router,
            max_collections=args.max_collections,
            principal=_permission_principal(args.principal_profile),
            sandbox_enabled=not args.disable_sandbox,
            skill_router_enabled=not args.disable_skill_router,
            skill_name=args.skill_name,
        )
        return

    if args.command == "agent-v3-15" and args.agent315_command == "resume":
        run_agent315_resume(
            run_id=args.run_id,
            action=args.action,
            step_arguments_json=args.step_arguments,
            comment=args.comment,
            api_base=args.api_base,
        )
        return

    if args.command == "agent-v3-15":
        run_agent315_recover(run_id=args.run_id, api_base=args.api_base)
        return

    if args.command == "agent-v3-16" and args.agent316_command == "ask":
        run_agent316_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            collection=args.collection,
            top_k=args.top_k,
            mode=args.mode,
            filter_path=args.filter_path,
            max_iterations=args.max_iterations,
            stream=not args.json,
            api_base=args.api_base,
        )
        return

    if args.command == "agent-v3-16" and args.agent316_command == "resume":
        run_agent315_resume(
            run_id=args.run_id,
            action=args.action,
            step_arguments_json=args.step_arguments,
            comment=args.comment,
            api_base=args.api_base,
        )
        return

    if args.command == "agent-v3-16":
        run_agent316_inspect(run_id=args.run_id, api_base=args.api_base)
        return

    if args.command == "agent-v3-17" and args.agent317_command == "ask":
        run_agent317_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            tenant_id=args.tenant_id,
            user_id=args.user_id,
            assistant_id=args.assistant_id,
            collection=args.collection,
            top_k=args.top_k,
            mode=args.mode,
            max_iterations=args.max_iterations,
            stream=not args.json,
            api_base=args.api_base,
        )
        return

    if args.command == "agent-v3-17" and args.agent317_command == "resume":
        run_agent315_resume(
            run_id=args.run_id,
            action=args.action,
            step_arguments_json=args.step_arguments,
            comment=args.comment,
            api_base=args.api_base,
        )
        return

    if args.command == "agent-v3-17" and args.agent317_command == "recover":
        run_agent315_recover(run_id=args.run_id, api_base=args.api_base)
        return

    if args.command == "agent-v3-17" and args.agent317_command == "inspect":
        run_agent316_inspect(run_id=args.run_id, api_base=args.api_base)
        return

    if args.command == "agent-v3-17":
        run_agent317_memory(
            action=args.action,
            memory_id=args.memory_id,
            kind=args.kind,
            content=args.content,
            tenant_id=args.tenant_id,
            user_id=args.user_id,
            assistant_id=args.assistant_id,
            api_base=args.api_base,
        )
        return

    if args.command == "agent-v3-10-3" and args.agent3103_command == "ask":
        run_agent3103_ask(
            question=args.question,
            conversation_id=args.conversation_id,
            memory_window=args.memory_window,
            memory_compaction_enabled=not args.disable_memory_compaction,
            memory_compaction_trigger_turns=args.memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=args.memory_compaction_trigger_tokens,
            top_k=args.top_k,
            mode=args.mode,
            max_steps=args.max_steps,
            max_retries=args.max_retries,
            filter_path=args.filter_path,
            context_max_chunks=args.context_max_chunks,
            context_token_budget=args.context_token_budget,
            thread_id=args.thread_id,
            max_parallel_searches=args.max_parallel_searches,
            simulate_transient_search_failure=args.simulate_transient_search_failure,
            stream=not args.json,
            api_base=args.api_base,
        )
        return

    if args.command == "agent-v3-10-3" and args.agent3103_command == "history":
        run_agent3103_history(
            thread_id=args.thread_id,
            limit=args.limit,
            api_base=args.api_base,
        )
        return


def run_mcp312(
    command: str,
    server_name: str | None = None,
    tool_name: str | None = None,
    arguments_json: str = "{}",
) -> None:
    """运行 V3.12 MCP 学习命令，并输出稳定 JSON。"""

    if command == "serve-demo":
        from obsidian_rag.v3_12.servers.demo_server import mcp

        mcp.run(transport="stdio")
        return
    if command == "serve-rag":
        from obsidian_rag.v3_12.servers.rag_server import mcp

        mcp.run(transport="stdio")
        return

    service = get_mcp_service()
    if command == "servers":
        payload = [server.model_dump(mode="json") for server in service.list_servers()]
    elif command == "tools":
        payload = asyncio.run(service.list_tools(server_name)).model_dump(mode="json")
    elif command == "call" and server_name and tool_name:
        try:
            arguments = json.loads(arguments_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--arguments 必须是合法 JSON object: {exc}") from exc
        if not isinstance(arguments, dict):
            raise ValueError("--arguments 必须解析为 JSON object")
        payload = asyncio.run(
            service.call_tool(
                McpCallRequest(
                    server_name=server_name,
                    tool_name=tool_name,
                    arguments=arguments,
                )
            )
        ).model_dump(mode="json")
    else:
        raise ValueError(f"Unsupported V3.12 MCP command: {command}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_agent3121_ask(
    question: str,
    conversation_id: str | None = None,
    collection: str | None = None,
    memory_window: int = 3,
    memory_compaction_enabled: bool = True,
    memory_compaction_trigger_turns: int = 4,
    memory_compaction_trigger_tokens: int = 3000,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 4,
    max_retries: int = 1,
    filter_path: str | None = None,
    context_max_chunks: int = 6,
    context_token_budget: int = 4000,
    api_base: str = "http://127.0.0.1:8020",
    stream: bool = True,
    mcp_enabled: bool | None = None,
    mcp_tool_names: list[str] | None = None,
    collection_router_enabled: bool | None = None,
    max_collections: int | None = None,
    principal: dict | None = None,
    sandbox_enabled: bool | None = None,
    skill_router_enabled: bool | None = None,
    skill_name: str | None = None,
) -> None:
    """调用 V3.12.1 公共 Core；SSE 只打印最终可见 answer_delta。"""

    payload = {
        "question": question,
        "conversation_id": conversation_id,
        "collection": collection,
        "memory_window": memory_window,
        "memory_compaction_enabled": memory_compaction_enabled,
        "memory_compaction_trigger_turns": memory_compaction_trigger_turns,
        "memory_compaction_trigger_tokens": memory_compaction_trigger_tokens,
        "top_k": top_k,
        "mode": mode,
        "filters": {"path": filter_path} if filter_path else None,
        "max_steps": max_steps,
        "max_retries": max_retries,
        "context_max_chunks": context_max_chunks,
        "context_token_budget": context_token_budget,
    }
    if mcp_enabled is not None:
        payload["mcp_enabled"] = mcp_enabled
        payload["mcp_tool_names"] = mcp_tool_names
    if collection_router_enabled is not None:
        payload["collection_router_enabled"] = collection_router_enabled
        payload["max_collections"] = max_collections or 2
    if principal is not None:
        payload["principal"] = principal
    if sandbox_enabled is not None:
        payload["sandbox_enabled"] = sandbox_enabled
    if skill_router_enabled is not None:
        payload["skill_router_enabled"] = skill_router_enabled
        payload["skill_name"] = skill_name
    base = api_base.rstrip("/")
    if not stream:
        response = httpx.post(f"{base}/agent/ask", json=payload, timeout=None)
        response.raise_for_status()
        result = response.json()
        agent = result.get("agent_response") or {}
        print(agent.get("answer", "").strip())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    current_event = "message"
    final_response = None
    with httpx.stream(
        "POST",
        f"{base}/agent/ask/stream",
        json=payload,
        headers={"Accept": "text/event-stream"},
        timeout=None,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue
            if not line.startswith("data:"):
                continue
            event = json.loads(line.split(":", 1)[1].strip())
            data = event.get("data", {})
            if current_event == "answer_delta":
                print(data.get("delta", ""), end="", flush=True)
            elif current_event in {"run_waiting_for_approval", "run_succeeded"}:
                final_response = data.get("response")
    print()
    if final_response:
        print(json.dumps(final_response, ensure_ascii=False, indent=2))


def run_agent3123_mcp(
    command: str,
    *,
    api_base: str,
    server_name: str | None = None,
    reconnect: bool = False,
    tool_name: str | None = None,
    arguments_json: str = "{}",
) -> None:
    """调用 V3.12.3 MCP Runtime 管理接口。"""

    base = api_base.rstrip("/")
    if command == "mcp-status":
        response = httpx.get(f"{base}/mcp/runtime", timeout=None)
    elif command == "mcp-refresh":
        response = httpx.post(
            f"{base}/mcp/refresh",
            params={"server_name": server_name, "reconnect": reconnect},
            timeout=None,
        )
    elif command == "mcp-call" and tool_name:
        arguments = json.loads(arguments_json)
        if not isinstance(arguments, dict):
            raise ValueError("--arguments 必须解析为 JSON object")
        response = httpx.post(
            f"{base}/mcp/call",
            json={"name": tool_name, "arguments": arguments},
            timeout=None,
        )
    else:
        raise ValueError(f"Unsupported V3.12.3 command: {command}")
    response.raise_for_status()
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))


def run_agent3124_collections(
    command: str,
    *,
    api_base: str,
    question: str | None = None,
    collection: str | None = None,
    router_enabled: bool = True,
    max_collections: int = 2,
) -> None:
    """调用 V3.12.4 Knowledge Base Registry 和 Collection Router 调试接口。"""

    base = api_base.rstrip("/")
    if command == "collections":
        response = httpx.get(f"{base}/collections/runtime", timeout=None)
    elif command == "route" and question:
        response = httpx.post(
            f"{base}/collections/route",
            json={
                "question": question,
                "collection": collection,
                "collection_router_enabled": router_enabled,
                "max_collections": max_collections,
            },
            timeout=None,
        )
    else:
        raise ValueError(f"Unsupported V3.12.4 command: {command}")
    response.raise_for_status()
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))


def run_agent313_permission(
    command: str,
    *,
    api_base: str,
    tool_name: str | None = None,
    arguments_json: str = "{}",
    principal_profile: str = "standard",
    limit: int = 20,
) -> None:
    """调用 V3.13 独立 Policy 与审计接口。"""

    base = api_base.rstrip("/")
    if command == "policy" and tool_name:
        arguments = json.loads(arguments_json)
        if not isinstance(arguments, dict):
            raise ValueError("--arguments 必须解析为 JSON object")
        response = httpx.post(
            f"{base}/permissions/evaluate",
            json={
                "principal": _permission_principal(principal_profile),
                "action": {
                    "step_id": "cli_policy_debug",
                    "kind": "tool",
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "collections": [],
                },
            },
            timeout=None,
        )
    elif command == "audit":
        response = httpx.get(f"{base}/permissions/audit", params={"limit": limit}, timeout=None)
    else:
        raise ValueError(f"Unsupported V3.13 command: {command}")
    response.raise_for_status()
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))


def _permission_principal(profile: str) -> dict:
    if profile == "knowledge-only":
        return {
            "subject_id": "cli_knowledge_only",
            "roles": ["user"],
            "permissions": ["knowledge.read"],
            "tool_allowlist": ["search_notes"],
            "allowed_collections": ["*"],
        }
    if profile == "restricted":
        return {
            "subject_id": "cli_restricted",
            "roles": ["restricted"],
            "permissions": [],
            "tool_allowlist": [],
            "allowed_collections": [],
        }
    if profile == "writer":
        return {
            "subject_id": "cli_writer",
            "roles": ["user"],
            "permissions": ["knowledge.read", "tool.read", "tool.write"],
            "tool_allowlist": ["search_notes", "demo::*", "local::*"],
            "allowed_collections": ["*"],
        }
    if profile == "sandbox":
        return {
            "subject_id": "cli_sandbox",
            "roles": ["user"],
            "permissions": [
                "knowledge.read",
                "tool.read",
                "sandbox.read",
                "sandbox.write",
                "sandbox.execute",
            ],
            "tool_allowlist": ["search_notes", "demo::*", "sandbox::*"],
            "allowed_collections": ["*"],
        }
    return {
        "subject_id": "cli_standard",
        "roles": ["user"],
        "permissions": ["knowledge.read", "tool.read"],
        "tool_allowlist": ["search_notes", "demo::*"],
        "allowed_collections": ["*"],
    }


def run_agent314_sandbox(
    *,
    api_base: str,
    tool_name: str,
    run_id: str,
    arguments_json: str,
    principal_profile: str,
) -> None:
    arguments = json.loads(arguments_json)
    if not isinstance(arguments, dict):
        raise ValueError("--arguments 必须解析为 JSON object")
    response = httpx.post(
        f"{api_base.rstrip('/')}/sandbox/call",
        json={
            "run_id": run_id,
            "name": f"sandbox::{tool_name}",
            "arguments": arguments,
            "principal": _permission_principal(principal_profile),
        },
        timeout=None,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))


def run_agent315_resume(
    *,
    run_id: str,
    action: str,
    step_arguments_json: str,
    comment: str | None,
    api_base: str,
) -> None:
    step_arguments = json.loads(step_arguments_json)
    if not isinstance(step_arguments, dict):
        raise ValueError("--step-arguments 必须解析为 JSON object")
    response = httpx.post(
        f"{api_base.rstrip('/')}/approvals/{run_id}/resume",
        json={
            "action": action,
            "comment": comment,
            "step_arguments": step_arguments,
        },
        timeout=None,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))


def run_agent315_recover(*, run_id: str, api_base: str) -> None:
    response = httpx.post(
        f"{api_base.rstrip('/')}/recoveries/{run_id}/retry",
        timeout=None,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))


def run_agent316_ask(
    *,
    question: str,
    conversation_id: str | None,
    collection: str | None,
    top_k: int,
    mode: SearchMode,
    filter_path: str | None,
    max_iterations: int,
    stream: bool,
    api_base: str,
) -> None:
    """调用 V3.16；SSE 输出最终答案，并在终态打印 DeepAgents 原生响应。"""

    payload = {
        "question": question,
        "conversation_id": conversation_id,
        "collection": collection,
        "top_k": top_k,
        "mode": mode,
        "filters": {"path": filter_path} if filter_path else None,
        "max_iterations": max_iterations,
    }
    base = api_base.rstrip("/")
    if not stream:
        response = httpx.post(f"{base}/agent/ask", json=payload, timeout=None)
        response.raise_for_status()
        result = response.json()
        print((result.get("agent_response") or {}).get("answer", "").strip())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    current_event = "message"
    final_response = None
    with httpx.stream(
        "POST",
        f"{base}/agent/ask/stream",
        json=payload,
        headers={"Accept": "text/event-stream"},
        timeout=None,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue
            if not line.startswith("data:"):
                continue
            event = json.loads(line.split(":", 1)[1].strip())
            data = event.get("data", {})
            if current_event == "answer_delta":
                print(data.get("delta", ""), end="", flush=True)
            elif current_event in {"run_waiting_for_approval", "run_succeeded", "run_failed"}:
                final_response = data.get("response")
    print()
    if final_response:
        print(json.dumps(final_response, ensure_ascii=False, indent=2))


def run_agent316_inspect(*, run_id: str, api_base: str) -> None:
    response = httpx.get(
        f"{api_base.rstrip('/')}/agent/runs/{run_id}",
        timeout=None,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))


def run_agent317_ask(
    *,
    question: str,
    conversation_id: str | None,
    tenant_id: str,
    user_id: str,
    assistant_id: str,
    collection: str | None,
    top_k: int,
    mode: SearchMode,
    max_iterations: int,
    stream: bool,
    api_base: str,
) -> None:
    payload = {
        "question": question,
        "conversation_id": conversation_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "assistant_id": assistant_id,
        "collection": collection,
        "top_k": top_k,
        "mode": mode,
        "max_iterations": max_iterations,
    }
    base = api_base.rstrip("/")
    if not stream:
        response = httpx.post(f"{base}/agent/ask", json=payload, timeout=None)
        response.raise_for_status()
        result = response.json()
        print((result.get("agent_response") or {}).get("answer", "").strip())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    current_event = "message"
    final_response = None
    with httpx.stream(
        "POST",
        f"{base}/agent/ask/stream",
        json=payload,
        headers={"Accept": "text/event-stream"},
        timeout=None,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue
            if not line.startswith("data:"):
                continue
            event = json.loads(line.split(":", 1)[1].strip())
            data = event.get("data", {})
            if current_event == "answer_delta":
                print(data.get("delta", ""), end="", flush=True)
            elif current_event == "context_summary":
                print("\n[context summarized]", flush=True)
            elif current_event in {"run_waiting_for_approval", "run_succeeded", "run_failed"}:
                final_response = data.get("response")
    print()
    if final_response:
        print(json.dumps(final_response, ensure_ascii=False, indent=2))


def run_agent317_memory(
    *,
    action: str,
    memory_id: str | None,
    kind: str,
    content: str | None,
    tenant_id: str,
    user_id: str,
    assistant_id: str,
    api_base: str,
) -> None:
    base = api_base.rstrip("/")
    scope = {"tenant_id": tenant_id, "user_id": user_id, "assistant_id": assistant_id}
    if action == "list":
        response = httpx.get(f"{base}/memories", params=scope, timeout=None)
    elif action == "put":
        if not content:
            raise SystemExit("memory put requires --content")
        response = httpx.put(
            f"{base}/memories",
            json={**scope, "memory_id": memory_id, "kind": kind, "content": content},
            timeout=None,
        )
    else:
        if not memory_id:
            raise SystemExit("memory delete requires --memory-id")
        response = httpx.delete(f"{base}/memories/{memory_id}", params=scope, timeout=None)
    response.raise_for_status()
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))


def run_agent3122_rerank(
    query: str,
    *,
    collection: str | None = None,
    collections: list[str] | None = None,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    api_base: str = "http://127.0.0.1:8020",
) -> None:
    """调用 V3.12.2 独立重排接口并打印排序前后数据。"""

    response = httpx.post(
        f"{api_base.rstrip('/')}/rerank/search",
        json={
            "query": query,
            "collection": collection,
            "collections": collections or [],
            "top_k": top_k,
            "mode": mode,
        },
        timeout=None,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))


def run_retrieval_eval(
    dataset_path: Path,
    config: RagConfig,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    output_path: Path | None = None,
    retrieval_service=None,
) -> None:
    dataset = load_eval_dataset(dataset_path)
    service = retrieval_service or RetrievalService(config)
    evaluator = RetrievalEvaluator(service)
    report = evaluator.evaluate_dataset(dataset, top_k=top_k, mode=mode, output_path=output_path)
    print(f"Examples: {report.summary.example_count}")
    print(f"Mode: {report.mode}")
    print(f"Top-K: {report.top_k}")
    print(f"Hit rate@{top_k}: {report.summary.hit_rate_at_k:.4f}")
    print(f"MRR: {report.summary.mean_reciprocal_rank:.4f}")
    print(f"Source recall: {report.summary.mean_source_recall:.4f}")
    if output_path is not None:
        print(f"Saved report: {output_path}")


def run_agent39_eval(
    dataset_path: Path,
    config: RagConfig | None = None,
    output_path: Path | None = None,
    memory_db_path: Path | None = None,
    retrieval_service=None,
    chat_client=None,
    agent_service=None,
) -> None:
    """从 YAML 批量运行 V3.8.1 Agent，并输出 V3.9 行为评测摘要。"""

    dataset = load_agent_eval_dataset(dataset_path)
    if agent_service is None:
        if config is None:
            raise ValueError("config is required when agent_service is not provided")
        service = retrieval_service or RetrievalService(config)
        memory_store = SQLite381ConversationMemoryStore(memory_db_path or default_agent_eval_memory_db_path())
        agent = Agent381Service(
            retrieval_service=service,
            chat_client=chat_client,
            chat_client_factory=lambda: OpenAIChatClient(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.chat_model,
            ),
            memory_store=memory_store,
        )
    else:
        agent = agent_service

    report = AgentEvaluator(agent).evaluate_dataset(dataset, output_path=output_path)
    print(f"Cases: {report.summary.case_count}")
    print(f"Passed: {report.summary.passed_count}")
    print(f"Pass rate: {report.summary.pass_rate:.4f}")
    print(f"Mean score: {report.summary.mean_score:.4f}")
    for case in report.cases:
        status = "PASS" if case.passed else "FAIL"
        print(f"{status} | {case.case_id} | score={case.score:.4f}")
        for check in case.checks:
            if not check.passed:
                print(f"  - {check.name}: {check.detail}")
    if output_path is not None:
        print(f"Saved report: {output_path}")


def run_agent_ask(
    question: str,
    config: RagConfig,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 2,
    retrieval_service=None,
    chat_client=None,
) -> None:
    service = retrieval_service or RetrievalService(config)
    agent = AgentService(
        retrieval_service=service,
        chat_client=chat_client,
        chat_client_factory=lambda: OpenAIChatClient(api_key=config.api_key, base_url=config.base_url, model=config.chat_model),
    )
    response = agent.ask(AgentAskRequest(question=question, top_k=top_k, mode=mode, max_steps=max_steps))
    print(response.answer.strip())
    if response.sources:
        _print_sources(response.sources)
    print("\nTrace:")
    for index, step in enumerate(response.trace, start=1):
        parts = [f"{index}. {step.step_type}"]
        if step.decision:
            parts.append(f"decision={step.decision}")
        if step.tool_name:
            parts.append(f"tool={step.tool_name}")
        if step.query:
            parts.append(f"query={step.query}")
        if step.result_count is not None:
            parts.append(f"results={step.result_count}")
        if step.reason:
            parts.append(f"reason={step.reason}")
        print(" | ".join(parts))


def run_agent31_ask(
    question: str,
    config: RagConfig,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 1,
    retrieval_service=None,
    router_chat_client=None,
    chat_client=None,
) -> None:
    service = retrieval_service or RetrievalService(config)
    agent = Agent31Service(
        router_service=RouterService(
            chat_client=router_chat_client,
            chat_client_factory=lambda: OpenAIChatClient(api_key=config.api_key, base_url=config.base_url, model=config.chat_model),
        ),
        retrieval_service=service,
        chat_client=chat_client,
        chat_client_factory=lambda: OpenAIChatClient(api_key=config.api_key, base_url=config.base_url, model=config.chat_model),
    )
    response = agent.ask(Agent31AskRequest(question=question, top_k=top_k, mode=mode, max_steps=max_steps))
    print(response.answer.strip())
    if response.sources:
        _print_sources(response.sources)
    print("\nRouter:")
    router_parts = [
        f"action={response.router.action}",
        f"intent={response.router.intent}",
    ]
    if response.router.search_query:
        router_parts.append(f"query={response.router.search_query}")
    if response.router.reason:
        router_parts.append(f"reason={response.router.reason}")
    print(" | ".join(router_parts))
    print("\nTrace:")
    for index, step in enumerate(response.trace, start=1):
        parts = [f"{index}. {step.step_type}"]
        if step.decision:
            parts.append(f"decision={step.decision}")
        if step.tool_name:
            parts.append(f"tool={step.tool_name}")
        if step.query:
            parts.append(f"query={step.query}")
        if step.result_count is not None:
            parts.append(f"results={step.result_count}")
        if step.reason:
            parts.append(f"reason={step.reason}")
        print(" | ".join(parts))


def run_agent32_ask(
    question: str,
    config: RagConfig,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 1,
    retrieval_service=None,
    chat_client=None,
) -> None:
    service = retrieval_service or RetrievalService(config)
    agent = Agent32Service(
        retrieval_service=service,
        chat_client=chat_client,
        chat_client_factory=lambda: OpenAIChatClient(api_key=config.api_key, base_url=config.base_url, model=config.chat_model),
    )
    response = agent.ask(Agent32AskRequest(question=question, top_k=top_k, mode=mode, max_steps=max_steps))
    print(response.answer.strip())
    if response.sources:
        _print_sources(response.sources)
    print("\nTool calls:")
    if response.tool_calls:
        for index, tool_call in enumerate(response.tool_calls, start=1):
            print(f"{index}. {tool_call.name} arguments={tool_call.arguments}")
    else:
        print("- none")
    print("\nTrace:")
    for index, step in enumerate(response.trace, start=1):
        parts = [f"{index}. {step.step_type}"]
        if step.tool_name:
            parts.append(f"tool={step.tool_name}")
        if step.query:
            parts.append(f"query={step.query}")
        if step.result_count is not None:
            parts.append(f"results={step.result_count}")
        if step.reason:
            parts.append(f"reason={step.reason}")
        print(" | ".join(parts))


def run_agent33_ask(
    question: str,
    config: RagConfig,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 1,
    retrieval_service=None,
    chat_client=None,
) -> None:
    service = retrieval_service or RetrievalService(config)
    agent = Agent33Service(
        retrieval_service=service,
        chat_client=chat_client,
        chat_client_factory=lambda: OpenAIChatClient(api_key=config.api_key, base_url=config.base_url, model=config.chat_model),
    )
    response = agent.ask(Agent33AskRequest(question=question, top_k=top_k, mode=mode, max_steps=max_steps))
    print(response.answer.strip())
    if response.sources:
        _print_sources(response.sources)
    print("\nTool calls:")
    if response.tool_calls:
        for index, tool_call in enumerate(response.tool_calls, start=1):
            print(f"{index}. {tool_call.name} arguments={tool_call.arguments}")
    else:
        print("- none")
    print("\nGraph path:")
    print(" -> ".join(response.graph_path) if response.graph_path else "- none")
    print("\nTrace:")
    for index, step in enumerate(response.trace, start=1):
        parts = [f"{index}. {step.node_name}:{step.step_type}"]
        if step.tool_name:
            parts.append(f"tool={step.tool_name}")
        if step.query:
            parts.append(f"query={step.query}")
        if step.result_count is not None:
            parts.append(f"results={step.result_count}")
        if step.reason:
            parts.append(f"reason={step.reason}")
        print(" | ".join(parts))


def run_agent34_plan(
    question: str,
    config: RagConfig,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 4,
    planner_service=None,
    chat_client=None,
) -> None:
    planner = planner_service or PlannerService(
        chat_client=chat_client,
        chat_client_factory=lambda: OpenAIChatClient(api_key=config.api_key, base_url=config.base_url, model=config.chat_model),
    )
    response = planner.plan(PlanRequest(question=question, top_k=top_k, mode=mode, max_steps=max_steps))
    print(f"Goal: {response.plan.goal}")
    print("\nPlan:")
    for step in response.plan.steps:
        parts = [step.id, step.kind]
        if step.query:
            parts.append(f"query={step.query}")
        if step.instruction:
            parts.append(f"instruction={step.instruction}")
        if step.depends_on:
            parts.append(f"depends_on={','.join(step.depends_on)}")
        if step.reason:
            parts.append(f"reason={step.reason}")
        print(" | ".join(parts))
    print("\nGraph path:")
    print(" -> ".join(response.graph_path) if response.graph_path else "- none")
    print("\nTrace:")
    for index, step in enumerate(response.trace, start=1):
        parts = [f"{index}. {step.node_name}:{step.step_type}"]
        if step.reason:
            parts.append(f"reason={step.reason}")
        if step.metadata:
            parts.append(f"metadata={step.metadata}")
        print(" | ".join(parts))


def run_agent35_ask(
    question: str,
    config: RagConfig,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 4,
    retrieval_service=None,
    chat_client=None,
    agent_service=None,
) -> None:
    service = retrieval_service or RetrievalService(config)
    agent = agent_service or Agent35Service(
        retrieval_service=service,
        chat_client=chat_client,
        chat_client_factory=lambda: OpenAIChatClient(api_key=config.api_key, base_url=config.base_url, model=config.chat_model),
    )
    response = agent.ask(Agent35AskRequest(question=question, top_k=top_k, mode=mode, max_steps=max_steps))
    print(f"Run: {response.run_id}")
    print(response.answer.strip())
    if response.sources:
        _print_sources(response.sources)
    print("\nStep results:")
    for result in response.step_results:
        parts = [result.step_id, result.kind]
        if result.tool_name:
            parts.append(f"tool={result.tool_name}")
        parts.append(f"status={result.status}")
        if result.query:
            parts.append(f"query={result.query}")
        parts.append(f"results={result.result_count}")
        if result.error:
            parts.append(f"error={result.error}")
        print(" | ".join(parts))
    print("\nGraph path:")
    print(" -> ".join(response.graph_path) if response.graph_path else "- none")
    print("\nTrace:")
    for index, step in enumerate(response.trace, start=1):
        parts = [f"{index}. {step.node_name}:{step.step_type}"]
        if step.step_id:
            parts.append(f"step={step.step_id}")
        if step.tool_name:
            parts.append(f"tool={step.tool_name}")
        if step.query:
            parts.append(f"query={step.query}")
        if step.result_count is not None:
            parts.append(f"results={step.result_count}")
        if step.reason:
            parts.append(f"reason={step.reason}")
        print(" | ".join(parts))


def run_agent36_ask(
    question: str,
    config: RagConfig,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 4,
    max_retries: int = 1,
    filter_path: str | None = None,
    retrieval_service=None,
    chat_client=None,
    agent_service=None,
) -> None:
    service = retrieval_service or RetrievalService(config)
    agent = agent_service or Agent36Service(
        retrieval_service=service,
        chat_client=chat_client,
        chat_client_factory=lambda: OpenAIChatClient(api_key=config.api_key, base_url=config.base_url, model=config.chat_model),
    )
    response = agent.ask(
        Agent36AskRequest(
            question=question,
            top_k=top_k,
            mode=mode,
            filters=SearchFilters(path=filter_path) if filter_path else None,
            max_steps=max_steps,
            max_retries=max_retries,
        )
    )
    print(f"Run: {response.run_id}")
    print(response.answer.strip())
    if response.sources:
        _print_sources(response.sources)
    print("\nEvidence check:")
    evidence = response.evidence_check
    print(f"sufficient={evidence.is_sufficient} | retry_count={evidence.retry_count} | reason={evidence.reason}")
    if evidence.missing_points:
        print("Missing points:")
        for point in evidence.missing_points:
            print(f"- {point}")
    if evidence.suggested_queries:
        print("Suggested queries:")
        for query in evidence.suggested_queries:
            print(f"- {query}")
    print("\nStep results:")
    _print_step_results(response.step_results)
    if response.retry_step_results:
        print("\nRetry step results:")
        _print_step_results(response.retry_step_results)
    print("\nGraph path:")
    print(" -> ".join(response.graph_path) if response.graph_path else "- none")
    print("\nTrace:")
    for index, step in enumerate(response.trace, start=1):
        parts = [f"{index}. {step.node_name}:{step.step_type}"]
        if step.step_id:
            parts.append(f"step={step.step_id}")
        if step.tool_name:
            parts.append(f"tool={step.tool_name}")
        if step.query:
            parts.append(f"query={step.query}")
        if step.result_count is not None:
            parts.append(f"results={step.result_count}")
        if step.reason:
            parts.append(f"reason={step.reason}")
        print(" | ".join(parts))


def run_agent37_ask(
    question: str,
    config: RagConfig,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 4,
    max_retries: int = 1,
    filter_path: str | None = None,
    context_max_chunks: int = 6,
    context_token_budget: int = 4000,
    retrieval_service=None,
    chat_client=None,
    agent_service=None,
) -> None:
    service = retrieval_service or RetrievalService(config)
    agent = agent_service or Agent37Service(
        retrieval_service=service,
        chat_client=chat_client,
        chat_client_factory=lambda: OpenAIChatClient(api_key=config.api_key, base_url=config.base_url, model=config.chat_model),
    )
    response = agent.ask(
        Agent37AskRequest(
            question=question,
            top_k=top_k,
            mode=mode,
            filters=SearchFilters(path=filter_path) if filter_path else None,
            max_steps=max_steps,
            max_retries=max_retries,
            context_max_chunks=context_max_chunks,
            context_token_budget=context_token_budget,
        )
    )
    print(f"Run: {response.run_id}")
    print(response.answer.strip())
    if response.sources:
        _print_sources(response.sources)
    print("\nEvidence check:")
    evidence = response.evidence_check
    print(f"sufficient={evidence.is_sufficient} | retry_count={evidence.retry_count} | reason={evidence.reason}")
    print("\nContext bundle:")
    bundle = response.context_bundle
    print(f"{bundle.context_summary} | token_budget={bundle.token_budget}")
    for chunk in bundle.included_chunks:
        chunk_label = chunk.chunk_id or "-"
        print(f"included: {chunk.step_id} | {chunk_label} | {chunk.source} | score={chunk.score:.4f}")
    for chunk in bundle.excluded_chunks:
        chunk_label = chunk.chunk_id or "-"
        reason = chunk.reason or "-"
        print(f"excluded: {chunk.step_id} | {chunk_label} | {chunk.source} | score={chunk.score:.4f} | reason={reason}")
    print("\nStep results:")
    _print_step_results(response.step_results)
    if response.retry_step_results:
        print("\nRetry step results:")
        _print_step_results(response.retry_step_results)
    print("\nGraph path:")
    print(" -> ".join(response.graph_path) if response.graph_path else "- none")
    print("\nTrace:")
    for index, step in enumerate(response.trace, start=1):
        parts = [f"{index}. {step.node_name}:{step.step_type}"]
        if step.step_id:
            parts.append(f"step={step.step_id}")
        if step.tool_name:
            parts.append(f"tool={step.tool_name}")
        if step.query:
            parts.append(f"query={step.query}")
        if step.result_count is not None:
            parts.append(f"results={step.result_count}")
        if step.reason:
            parts.append(f"reason={step.reason}")
        print(" | ".join(parts))


def run_agent38_ask(
    question: str,
    config: RagConfig,
    conversation_id: str | None = None,
    memory_window: int = 3,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 4,
    max_retries: int = 1,
    filter_path: str | None = None,
    context_max_chunks: int = 6,
    context_token_budget: int = 4000,
    memory_db_path: Path | None = None,
    retrieval_service=None,
    chat_client=None,
    agent_service=None,
) -> None:
    if agent_service is None:
        service = retrieval_service or RetrievalService(config)
        memory_store = SQLiteConversationMemoryStore(memory_db_path or default_memory_db_path())
        agent = Agent38Service(
            retrieval_service=service,
            chat_client=chat_client,
            chat_client_factory=lambda: OpenAIChatClient(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.chat_model,
            ),
            memory_store=memory_store,
        )
    else:
        agent = agent_service
    response = agent.ask(
        Agent38AskRequest(
            question=question,
            conversation_id=conversation_id,
            memory_window=memory_window,
            top_k=top_k,
            mode=mode,
            filters=SearchFilters(path=filter_path) if filter_path else None,
            max_steps=max_steps,
            max_retries=max_retries,
            context_max_chunks=context_max_chunks,
            context_token_budget=context_token_budget,
        )
    )
    print(f"Run: {response.run_id}")
    print(f"Conversation: {response.conversation_id}")
    snapshot = response.memory_snapshot
    print(
        f"Memory: loaded={snapshot.loaded_turn_count} | total={snapshot.total_turn_count} "
        f"| omitted={snapshot.omitted_turn_count}"
    )
    for turn in snapshot.recent_turns:
        print(f"- {turn.user_message} -> {turn.assistant_message}")
    print(response.answer.strip())
    if response.sources:
        _print_sources(response.sources)
    print(
        f"\nMemory write: saved={response.memory_write.saved} "
        f"| turn={response.memory_write.turn_id or '-'}"
    )
    print("\nContext bundle:")
    print(f"{response.context_bundle.context_summary} | token_budget={response.context_bundle.token_budget}")
    print("\nGraph path:")
    print(" -> ".join(response.graph_path) if response.graph_path else "- none")
    print("\nTrace:")
    for index, step in enumerate(response.trace, start=1):
        parts = [f"{index}. {step.node_name}:{step.step_type}"]
        if step.result_count is not None:
            parts.append(f"results={step.result_count}")
        if step.reason:
            parts.append(f"reason={step.reason}")
        print(" | ".join(parts))


def run_agent381_ask(
    question: str,
    config: RagConfig,
    conversation_id: str | None = None,
    memory_window: int = 3,
    memory_compaction_enabled: bool = True,
    memory_compaction_trigger_turns: int = 4,
    memory_compaction_trigger_tokens: int = 3000,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 4,
    max_retries: int = 1,
    filter_path: str | None = None,
    context_max_chunks: int = 6,
    context_token_budget: int = 4000,
    collection: str | None = None,
    memory_db_path: Path | None = None,
    retrieval_service=None,
    chat_client=None,
    agent_service=None,
) -> None:
    if agent_service is None:
        service = retrieval_service or RetrievalService(config)
        memory_store = MySQLConversationMemoryStore()
        agent = Agent381Service(
            retrieval_service=service,
            chat_client=chat_client,
            chat_client_factory=lambda: OpenAIChatClient(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.chat_model,
            ),
            memory_store=memory_store,
        )
    else:
        agent = agent_service

    response = agent.ask(
        Agent381AskRequest(
            question=question,
            conversation_id=conversation_id,
            memory_window=memory_window,
            memory_compaction_enabled=memory_compaction_enabled,
            memory_compaction_trigger_turns=memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=memory_compaction_trigger_tokens,
            top_k=top_k,
            mode=mode,
            filters=SearchFilters(path=filter_path) if filter_path else None,
            max_steps=max_steps,
            max_retries=max_retries,
            context_max_chunks=context_max_chunks,
            context_token_budget=context_token_budget,
            collection=collection,
        )
    )
    print(f"Run: {response.run_id}")
    print(f"Conversation: {response.conversation_id}")
    snapshot = response.memory_snapshot
    print(
        f"Memory: loaded={snapshot.loaded_turn_count} | total={snapshot.total_turn_count} "
        f"| omitted={snapshot.omitted_turn_count}"
    )
    if snapshot.summary_text:
        print(f"Summary: {snapshot.summary_text}")
    for turn in snapshot.recent_turns:
        print(f"- {turn.user_message} -> {turn.assistant_message}")
    compaction = response.memory_compaction
    print(
        f"Compaction: compacted={compaction.compacted} | attempted={compaction.attempted} "
        f"| summarized={compaction.summarized_turn_count} | reason={compaction.reason}"
    )
    print(response.answer.strip())
    if response.sources:
        _print_sources(response.sources)
    print(
        f"\nMemory write: saved={response.memory_write.saved} "
        f"| turn={response.memory_write.turn_id or '-'}"
    )
    print("\nContext bundle:")
    print(f"{response.context_bundle.context_summary} | token_budget={response.context_bundle.token_budget}")
    print("\nGraph path:")
    print(" -> ".join(response.graph_path) if response.graph_path else "- none")
    print("\nTrace:")
    for index, step in enumerate(response.trace, start=1):
        parts = [f"{index}. {step.node_name}:{step.step_type}"]
        if step.result_count is not None:
            parts.append(f"results={step.result_count}")
        if step.reason:
            parts.append(f"reason={step.reason}")
        print(" | ".join(parts))


def run_agent310_ask(
    question: str,
    config: RagConfig,
    conversation_id: str | None = None,
    memory_window: int = 3,
    memory_compaction_enabled: bool = True,
    memory_compaction_trigger_turns: int = 4,
    memory_compaction_trigger_tokens: int = 3000,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 4,
    max_retries: int = 1,
    filter_path: str | None = None,
    context_max_chunks: int = 6,
    context_token_budget: int = 4000,
    memory_db_path: Path | None = None,
    retrieval_service=None,
    chat_client=None,
    agent_service=None,
    runtime_service=None,
) -> None:
    """运行 V3.10 外壳并打印简洁的 Production Run 观察结果。"""

    if runtime_service is None:
        if agent_service is None:
            service = retrieval_service or RetrievalService(config)
            memory_store = MySQLConversationMemoryStore()
            agent = Agent381Service(
                retrieval_service=service,
                chat_client=chat_client,
                chat_client_factory=lambda: OpenAIChatClient(
                    api_key=config.api_key,
                    base_url=config.base_url,
                    model=config.chat_model,
                ),
                memory_store=memory_store,
            )
        else:
            agent = agent_service
        runtime = AgentRuntimeService(agent_service=agent, run_store=InMemoryRunStore())
    else:
        runtime = runtime_service

    response = runtime.ask(
        ProductionAskRequest(
            question=question,
            conversation_id=conversation_id,
            memory_window=memory_window,
            memory_compaction_enabled=memory_compaction_enabled,
            memory_compaction_trigger_turns=memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=memory_compaction_trigger_tokens,
            top_k=top_k,
            mode=mode,
            filters=SearchFilters(path=filter_path) if filter_path else None,
            max_steps=max_steps,
            max_retries=max_retries,
            context_max_chunks=context_max_chunks,
            context_token_budget=context_token_budget,
        )
    )
    run = response.run
    print(f"Production run: {run.run_id}")
    print(f"Status: {run.status}")
    if run.agent_run_id:
        print(f"Agent run: {run.agent_run_id}")
    if run.timing.duration_ms is not None:
        print(f"Duration: {run.timing.duration_ms} ms")
    if run.metrics:
        print(
            f"Graph nodes: {run.metrics.graph_node_count} | Trace events: {run.metrics.trace_event_count} "
            f"| Retrieval results: {run.metrics.retrieval_result_count}"
        )
        for tool in run.metrics.tool_summaries:
            print(
                f"Tool: {tool.tool_name} | calls={tool.call_count} | success={tool.success_count} "
                f"| failed={tool.failed_count} | results={tool.result_count}"
            )
        estimate = run.metrics.token_estimate
        print(f"Observed token estimate: {estimate.observed_total_tokens}")
    if run.error:
        print(f"Error: {run.error.error_type}: {run.error.message}")
    if response.agent_response:
        print(response.agent_response.answer.strip())


def run_agent3101_ask(*args, **kwargs) -> None:
    """V3.10.1 的 CLI 调试入口；Agent 运行仍复用 V3.10 Production Runtime。"""

    print("Agent Console JSON flow")
    run_agent310_ask(*args, **kwargs)


def run_agent3102_stream(
    question: str,
    config: RagConfig,
    conversation_id: str | None = None,
    memory_window: int = 3,
    memory_compaction_enabled: bool = True,
    memory_compaction_trigger_turns: int = 4,
    memory_compaction_trigger_tokens: int = 3000,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 4,
    max_retries: int = 1,
    filter_path: str | None = None,
    context_max_chunks: int = 6,
    context_token_budget: int = 4000,
    api_base: str = "http://127.0.0.1:8014",
) -> None:
    """调用 V3.10.2 HTTP SSE 接口，打印事实事件和最终答案。"""

    payload = {
        "question": question,
        "conversation_id": conversation_id,
        "memory_window": memory_window,
        "memory_compaction_enabled": memory_compaction_enabled,
        "memory_compaction_trigger_turns": memory_compaction_trigger_turns,
        "memory_compaction_trigger_tokens": memory_compaction_trigger_tokens,
        "top_k": top_k,
        "mode": mode,
        "filters": {"path": filter_path} if filter_path else None,
        "max_steps": max_steps,
        "max_retries": max_retries,
        "context_max_chunks": context_max_chunks,
        "context_token_budget": context_token_budget,
    }
    current_event = "message"
    with httpx.stream(
        "POST",
        f"{api_base.rstrip('/')}/agent/ask/stream",
        json=payload,
        headers={"Accept": "text/event-stream"},
        timeout=None,
    ) as response:
        response.raise_for_status()
        print("V3.10.2 SSE events")
        for line in response.iter_lines():
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue
            if not line.startswith("data:"):
                continue
            event = json.loads(line.split(":", 1)[1].strip())
            detail = event.get("detail", "")
            print(f"- {current_event}: {detail}")
            if current_event == "run_succeeded":
                final_response = event.get("data", {}).get("response", {}).get("agent_response")
                if final_response:
                    print("\nAnswer:")
                    print(final_response.get("answer", "").strip())


def run_chunking3112_compare(
    config: RagConfig,
    query: str,
    path: Path | None = None,
    top_k: int = 4,
    langchain_parent_chars: int = 2000,
    langchain_child_chars: int = 400,
    llama_parent_tokens: int = 1024,
    llama_child_tokens: int = 256,
    semantic_breakpoint_percentile: int = 95,
    service: FrameworkComparisonService | None = None,
) -> None:
    """运行 V3.11.2 三框架策略对比并打印统一 JSON。"""

    service = service or FrameworkComparisonService(config)
    response = service.compare(
        FrameworkCompareRequest(
            path=str(path) if path else None,
            query=query,
            top_k=top_k,
            langchain_parent_chars=langchain_parent_chars,
            langchain_child_chars=langchain_child_chars,
            llama_parent_tokens=llama_parent_tokens,
            llama_child_tokens=llama_child_tokens,
            semantic_breakpoint_percentile=semantic_breakpoint_percentile,
        )
    )
    print(response.model_dump_json(indent=2))


def run_documents3111(
    command: str,
    config: RagConfig,
    path: Path | None = None,
    recreate: bool = False,
    query: str | None = None,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    collection: str | None = None,
    service: DoclingLearningService | None = None,
) -> None:
    """运行 V3.11.1 Docling 学习入口，并打印结构化 JSON。"""

    service = service or DoclingLearningService(config)
    path_value = str(path) if path else None
    if command == "convert":
        response = service.convert(DoclingPathRequest(path=path_value))
    elif command == "chunks":
        response = service.chunks(DoclingPathRequest(path=path_value))
    elif command == "ingest":
        response = service.ingest(DoclingIngestRequest(path=path_value, recreate=recreate, collection=collection))
    elif command == "search" and query:
        response = service.search(DoclingSearchRequest(query=query, top_k=top_k, mode=mode, collection=collection))
    else:
        raise ValueError(f"Unsupported V3.11.1 command: {command}")
    print(response.model_dump_json(indent=2))


def run_collections3113(
    command: str,
    config: RagConfig,
    question: str | None = None,
    collection: str | None = None,
    router_enabled: bool = True,
    max_collections: int = 2,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    registry_path: Path | None = None,
    service: CollectionRouterService | None = None,
) -> None:
    """运行 V3.11.3 Registry、Collection Router 和多库检索 JSON CLI。"""

    if service is None:
        registry = KnowledgeBaseRegistry(registry_path or get_registry_path())
        registry.load()
        service = CollectionRouterService(
            config=config,
            registry=registry,
            retrieval_service=RetrievalService(config),
            router=CollectionRouter(
                chat_client_factory=lambda: OpenAIChatClient(
                    api_key=config.api_key,
                    base_url=config.base_url,
                    model=config.chat_model,
                )
            ),
        )
    if command == "list":
        response = service.list_collections()
    elif command == "route" and question:
        response = service.route(
            CollectionRouteRequest(
                question=question,
                collection=collection,
                router_enabled=router_enabled,
                max_collections=max_collections,
            )
        )
    elif command == "search" and question:
        response = service.search(
            CollectionSearchRequest(
                question=question,
                collection=collection,
                router_enabled=router_enabled,
                max_collections=max_collections,
                top_k=top_k,
                mode=mode,
            )
        )
    else:
        raise ValueError(f"Unsupported V3.11.3 command: {command}")
    print(response.model_dump_json(indent=2))


def run_agent311_list(skill_root: Path) -> None:
    """打印 V3.11 Registry 发现的 Skill 元数据，不加载正文。"""

    registry = SkillRegistry(skill_root)
    manifests = registry.discover()
    print(f"Skill root: {registry.root}")
    print(f"Discovered: {len(manifests)}")
    for manifest in manifests:
        print(f"- {manifest.name} v{manifest.version} | {manifest.description}")
        if manifest.triggers:
            print(f"  triggers: {', '.join(manifest.triggers)}")
    if registry.errors:
        print("Errors:")
        for error in registry.errors:
            print(f"- {error}")


def run_agent311_ask(
    question: str,
    config: RagConfig,
    conversation_id: str | None = None,
    memory_window: int = 3,
    memory_compaction_enabled: bool = True,
    memory_compaction_trigger_turns: int = 4,
    memory_compaction_trigger_tokens: int = 3000,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 4,
    max_retries: int = 1,
    filter_path: str | None = None,
    context_max_chunks: int = 6,
    context_token_budget: int = 4000,
    collection: str | None = None,
    skill_name: str | None = None,
    skill_router_enabled: bool = True,
    skill_root: Path = Path("skills"),
    agent_service=None,
) -> None:
    """直接运行 V3.11 Skill Agent，打印 Skill 层和底层 Agent 事实。"""

    if agent_service is None:
        registry = SkillRegistry(skill_root)
        registry.discover()
        agent = SkillAgentService(
            retrieval_service=RetrievalService(config),
            registry=registry,
            chat_client_factory=lambda: OpenAIChatClient(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.chat_model,
            ),
            memory_store=MySQLConversationMemoryStore(),
        )
    else:
        agent = agent_service

    response = agent.ask(
        SkillAskRequest(
            question=question,
            conversation_id=conversation_id,
            memory_window=memory_window,
            memory_compaction_enabled=memory_compaction_enabled,
            memory_compaction_trigger_turns=memory_compaction_trigger_turns,
            memory_compaction_trigger_tokens=memory_compaction_trigger_tokens,
            top_k=top_k,
            mode=mode,
            filters=SearchFilters(path=filter_path) if filter_path else None,
            max_steps=max_steps,
            max_retries=max_retries,
            context_max_chunks=context_max_chunks,
            context_token_budget=context_token_budget,
            collection=collection,
            skill_name=skill_name,
            skill_router_enabled=skill_router_enabled,
        )
    )
    selection = response.skill_selection
    print(f"Skill: {selection.status} | {selection.selected_skill or '-'}")
    print(f"Reason: {selection.reason}")
    if response.loaded_skill:
        print(
            f"Loaded: {response.loaded_skill.name} | {response.loaded_skill.path} | "
            f"estimated_tokens={response.loaded_skill.estimated_tokens}"
        )
    print(f"\nAnswer:\n{response.agent_response.answer.strip()}")
    if response.agent_response.sources:
        _print_sources(response.agent_response.sources)
    print("\nSkill graph path:")
    print(" -> ".join(response.graph_path))
    print("\nSkill trace:")
    for index, event in enumerate(response.trace, start=1):
        selected = f" | skill={event.selected_skill}" if event.selected_skill else ""
        print(f"{index}. {event.node_name}:{event.event_type}{selected} | {event.reason}")


def run_agent3103_ask(
    question: str,
    conversation_id: str | None = None,
    memory_window: int = 3,
    memory_compaction_enabled: bool = True,
    memory_compaction_trigger_turns: int = 4,
    memory_compaction_trigger_tokens: int = 3000,
    top_k: int = 5,
    mode: SearchMode = "hybrid",
    max_steps: int = 4,
    max_retries: int = 1,
    filter_path: str | None = None,
    context_max_chunks: int = 6,
    context_token_budget: int = 4000,
    thread_id: str | None = None,
    max_parallel_searches: int = 4,
    simulate_transient_search_failure: bool = False,
    stream: bool = True,
    api_base: str = "http://127.0.0.1:8015",
) -> None:
    """调用 V3.10.3 Advanced Graph，并打印 messages/custom/updates 事件。"""

    payload = {
        "question": question,
        "conversation_id": conversation_id,
        "memory_window": memory_window,
        "memory_compaction_enabled": memory_compaction_enabled,
        "memory_compaction_trigger_turns": memory_compaction_trigger_turns,
        "memory_compaction_trigger_tokens": memory_compaction_trigger_tokens,
        "top_k": top_k,
        "mode": mode,
        "filters": {"path": filter_path} if filter_path else None,
        "max_steps": max_steps,
        "max_retries": max_retries,
        "context_max_chunks": context_max_chunks,
        "context_token_budget": context_token_budget,
        "thread_id": thread_id,
        "max_parallel_searches": max_parallel_searches,
        "simulate_transient_search_failure": simulate_transient_search_failure,
    }
    base = api_base.rstrip("/")
    if not stream:
        response = httpx.post(f"{base}/advanced/ask", json=payload, timeout=None)
        response.raise_for_status()
        result = response.json()
        print(f"Run: {result['run_id']} | Thread: {result['thread_id']}")
        print(result["answer"].strip())
        print("Graph path: " + " -> ".join(result.get("graph_path", [])))
        return

    current_event = "message"
    answer_started = False
    with httpx.stream(
        "POST",
        f"{base}/advanced/ask/stream",
        json=payload,
        headers={"Accept": "text/event-stream"},
        timeout=None,
    ) as response:
        response.raise_for_status()
        print("V3.10.3 LangGraph stream")
        for line in response.iter_lines():
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue
            if not line.startswith("data:"):
                continue
            event = json.loads(line.split(":", 1)[1].strip())
            data = event.get("data", {})
            if current_event == "answer_delta":
                if not answer_started:
                    print("\nAnswer stream:")
                    answer_started = True
                print(data.get("delta", ""), end="", flush=True)
                continue
            if answer_started:
                print()
                answer_started = False
            print(f"- {current_event}: {event.get('detail', '')}")
            if current_event == "run_succeeded":
                final_response = data.get("response", {})
                print(f"Thread: {final_response.get('thread_id', '-')}")


def run_agent3103_history(
    thread_id: str,
    limit: int = 20,
    api_base: str = "http://127.0.0.1:8015",
) -> None:
    """读取 V3.10.3 InMemorySaver 的轻量 State History。"""

    response = httpx.get(
        f"{api_base.rstrip('/')}/advanced/history/{thread_id}",
        params={"limit": limit},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    print(f"Thread: {payload['thread_id']} | checkpoints={len(payload['entries'])}")
    for entry in payload["entries"]:
        print(
            f"- checkpoint={entry.get('checkpoint_id') or '-'} "
            f"next={','.join(entry.get('next_nodes', [])) or '-'} "
            f"path={len(entry.get('graph_path', []))}"
        )


def run_agent381_compact(
    conversation_id: str,
    config: RagConfig,
    keep_recent_turns: int = 3,
    trigger_turns: int = 4,
    trigger_tokens: int = 3000,
    force: bool = True,
    memory_db_path: Path | None = None,
    memory_store=None,
    chat_client=None,
) -> None:
    store = memory_store or MySQLConversationMemoryStore()
    client = chat_client or OpenAIChatClient(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.chat_model,
    )
    result = Conversation381Compactor(memory_store=store, chat_client=client).compact(
        conversation_id=conversation_id,
        keep_recent_turns=keep_recent_turns,
        trigger_turns=trigger_turns,
        trigger_tokens=trigger_tokens,
        force=force,
    )
    snapshot = store.load_snapshot(conversation_id, window=keep_recent_turns)
    print(
        f"Compaction: compacted={result.compacted} | attempted={result.attempted} "
        f"| candidates={result.candidate_turn_count} | summarized={result.summarized_turn_count}"
    )
    print(f"Reason: {result.reason}")
    print(f"Summary through: {result.summary_through_turn_id or '-'}")
    print(f"Summary: {snapshot.summary_text or '-'}")
    print(f"Recent turns: {snapshot.loaded_turn_count} | total turns: {snapshot.total_turn_count}")


def _print_step_results(step_results) -> None:
    for result in step_results:
        parts = [result.step_id, result.kind]
        if result.tool_name:
            parts.append(f"tool={result.tool_name}")
        parts.append(f"status={result.status}")
        if result.query:
            parts.append(f"query={result.query}")
        parts.append(f"results={result.result_count}")
        if result.error:
            parts.append(f"error={result.error}")
        print(" | ".join(parts))


def _print_results(results) -> None:
    for index, result in enumerate(results, start=1):
        source = result.chunk.metadata.get("source", "unknown")
        title = result.chunk.metadata.get("title")
        heading = f"{index}. {source}"
        if title:
            heading += f" ({title})"
        print(f"{heading} score={result.score:.4f}")
        preview = " ".join(result.chunk.text.split())
        print(preview[:500])
        print()


def _print_sources(sources: list[str]) -> None:
    if not sources:
        return
    print("\nSources:")
    for source in sources:
        print(f"- {source}")


if __name__ == "__main__":
    main()
