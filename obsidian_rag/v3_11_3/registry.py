from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from obsidian_rag.v3_11_3.schemas import KnowledgeBaseManifest


class KnowledgeBaseRegistry:
    """从 YAML 加载可路由知识库元数据，并跳过无效条目。"""

    def __init__(self, path: Path):
        self.path = path.expanduser().resolve()
        self._manifests: list[KnowledgeBaseManifest] = []
        self.errors: list[str] = []

    def load(self) -> list[KnowledgeBaseManifest]:
        self._manifests = []
        self.errors = []
        try:
            payload = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            self.errors.append(f"{self.path}: {exc}")
            return []
        entries = payload.get("knowledge_bases") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            self.errors.append(f"{self.path}: knowledge_bases 必须是列表")
            return []

        seen_ids: set[str] = set()
        seen_collections: set[str] = set()
        for index, entry in enumerate(entries):
            try:
                manifest = KnowledgeBaseManifest.model_validate(entry)
                if manifest.id in seen_ids:
                    raise ValueError(f"重复 id: {manifest.id}")
                if manifest.collection in seen_collections:
                    raise ValueError(f"重复 collection: {manifest.collection}")
            except (ValidationError, ValueError, TypeError) as exc:
                self.errors.append(f"knowledge_bases[{index}]: {exc}")
                continue
            seen_ids.add(manifest.id)
            seen_collections.add(manifest.collection)
            self._manifests.append(manifest)
        return list(self._manifests)

    def list_manifests(self, *, enabled_only: bool = False) -> list[KnowledgeBaseManifest]:
        if not self._manifests and not self.errors:
            self.load()
        if enabled_only:
            return [manifest for manifest in self._manifests if manifest.enabled]
        return list(self._manifests)

    def get_by_collection(self, collection: str) -> KnowledgeBaseManifest | None:
        return next(
            (
                manifest
                for manifest in self.list_manifests(enabled_only=True)
                if manifest.collection == collection
            ),
            None,
        )
