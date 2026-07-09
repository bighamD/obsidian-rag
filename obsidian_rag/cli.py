from __future__ import annotations

import argparse
from pathlib import Path

from obsidian_rag.config import RagConfig
from obsidian_rag.config import load_config, resolve_ingest_path
from obsidian_rag.pipeline import answer, ingest_path, search
from obsidian_rag.prompting import format_sources
from obsidian_rag.v1.schemas import SearchMode
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
from obsidian_rag.llm import OpenAIChatClient


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

    search_parser = subparsers.add_parser("search", help="Retrieve relevant chunks without calling the LLM")
    search_parser.add_argument("query")
    search_parser.add_argument("--top-k", type=int, default=5)

    ask_parser = subparsers.add_parser("ask", help="Retrieve chunks and ask the configured LLM")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--top-k", type=int, default=5)

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

    args = parser.parse_args()
    config = load_config()

    if args.command == "ingest":
        path = resolve_ingest_path(args.path, config)
        document_count, chunk_count = ingest_path(path, config=config, recreate=args.recreate)
        print(f"Indexed {document_count} documents into {chunk_count} chunks.")
        return

    if args.command == "search":
        results = search(args.query, config=config, top_k=args.top_k)
        _print_results(results)
        return

    if args.command == "ask":
        response, results = answer(args.question, config=config, top_k=args.top_k)
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
