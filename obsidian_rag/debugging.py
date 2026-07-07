from __future__ import annotations

import os
from typing import Any


def is_debug_breakpoint_enabled(name: str, setting: str | None = None) -> bool:
    raw_setting = os.getenv("RAG_DEBUG_BREAKPOINTS", "") if setting is None else setting
    enabled = {item.strip() for item in raw_setting.split(",") if item.strip()}
    return "all" in enabled or name in enabled


def debug_breakpoint(name: str, **values: Any) -> None:
    if not is_debug_breakpoint_enabled(name):
        return

    print(f"\n[RAG DEBUG] breakpoint={name}")
    for key, value in values.items():
        print(f"[RAG DEBUG] {key}={_preview(value)}")
    breakpoint()


def _preview(value: Any, max_length: int = 500) -> str:
    text = repr(value)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."
