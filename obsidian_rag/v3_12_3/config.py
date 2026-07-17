from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from obsidian_rag.v3_12_3.schemas import McpServerRegistryConfig


_ENV_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def default_registry_path() -> Path:
    return Path(os.getenv("RAG_MCP_SERVER_REGISTRY", "mcp_servers.yaml")).expanduser().resolve()


def load_mcp_server_registry(path: Path | None = None) -> tuple[McpServerRegistryConfig, Path]:
    registry_path = (path or default_registry_path()).expanduser().resolve()
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    expanded = _expand_environment(payload)
    return McpServerRegistryConfig.model_validate(expanded), registry_path


def resolve_server_cwd(value: str | None, registry_path: Path) -> Path:
    if not value:
        return registry_path.parent
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = registry_path.parent / path
    return path.resolve()


def _expand_environment(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_environment(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_environment(item) for item in value]
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name == "PYTHON_EXECUTABLE":
            return sys.executable
        return os.getenv(name, match.group(0))

    return _ENV_PATTERN.sub(replace, value)
