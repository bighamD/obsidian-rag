from __future__ import annotations

from pathlib import Path

import yaml

from obsidian_rag.v3_9.schemas import AgentEvalDataset


def load_agent_eval_dataset(path: Path) -> AgentEvalDataset:
    """加载并校验包含 `cases` 的 Agent Eval YAML 文件。"""

    payload = yaml.safe_load(path.expanduser().read_text(encoding="utf-8")) or {}
    try:
        return AgentEvalDataset.model_validate(payload)
    except ValueError as exc:
        raise ValueError(f"invalid agent eval dataset: {path}") from exc
