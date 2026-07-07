from __future__ import annotations

import argparse
from pathlib import Path

from obsidian_rag.config import load_config, resolve_ingest_path
from obsidian_rag.pipeline import answer, ingest_path, search
from obsidian_rag.prompting import format_sources


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
