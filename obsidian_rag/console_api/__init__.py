"""Stable Agent Console API contract shared by current runtime versions."""

from obsidian_rag.console_api.routes import create_console_router, router

__all__ = ["create_console_router", "router"]
