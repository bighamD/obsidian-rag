from __future__ import annotations

import re
from pathlib import Path

import yaml

from obsidian_rag.core.skills.schemas import SkillDocument, SkillManifest


class SkillRegistry:
    """发现本地 SKILL.md，并在选中后按名称加载正文。"""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self._manifests: dict[str, SkillManifest] = {}
        self.errors: list[str] = []

    def discover(self) -> list[SkillManifest]:
        self._manifests = {}
        self.errors = []
        if not self.root.exists():
            return []
        for entry_file in sorted(self.root.rglob("SKILL.md")):
            if any(part.startswith(".") for part in entry_file.relative_to(self.root).parts):
                continue
            try:
                manifest = self._read_manifest(entry_file)
                if manifest.name in self._manifests:
                    raise ValueError(f"重复的 Skill 名称: {manifest.name}")
                self._manifests[manifest.name] = manifest
            except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
                self.errors.append(f"{entry_file}: {exc}")
        return list(self._manifests.values())

    def list_manifests(self) -> list[SkillManifest]:
        if not self._manifests and not self.errors:
            self.discover()
        return list(self._manifests.values())

    def load(self, name: str) -> SkillDocument:
        manifest = self._manifests.get(name)
        if manifest is None:
            self.discover()
            manifest = self._manifests.get(name)
        if manifest is None:
            raise KeyError(f"未知 Skill: {name}")
        entry_file = self.root / manifest.path
        raw_text = entry_file.read_text(encoding="utf-8")
        _, body = _split_front_matter(raw_text)
        return SkillDocument(
            **manifest.model_dump(),
            content=body.strip(),
            estimated_tokens=_estimate_tokens(body),
        )

    def _read_manifest(self, entry_file: Path) -> SkillManifest:
        raw_text = entry_file.read_text(encoding="utf-8")
        metadata, _ = _split_front_matter(raw_text)
        name = str(metadata.get("name") or entry_file.parent.name).strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            raise ValueError("name 只能包含小写字母、数字、下划线和连字符")
        description = str(metadata.get("description") or "").strip()
        if not description:
            raise ValueError("缺少 description")
        triggers = metadata.get("triggers") or []
        if isinstance(triggers, str):
            triggers = [triggers]
        if not isinstance(triggers, list):
            raise ValueError("triggers 必须是字符串列表")
        return SkillManifest(
            name=name,
            description=description,
            triggers=[str(trigger) for trigger in triggers],
            version=str(metadata.get("version") or "1.0"),
            entry_file=entry_file.name,
            path=entry_file.relative_to(self.root).as_posix(),
        )


def build_skill_context(question: str, skill: SkillDocument) -> str:
    """把已选 Skill 方法正文投影到 Planner 输入，不执行 Skill scripts。"""

    return (
        "[Selected Skill Context]\n"
        f"name: {skill.name}\n"
        f"description: {skill.description}\n"
        "method:\n"
        f"{skill.content}\n\n"
        "[User Question]\n"
        f"{question}"
    )


def _split_front_matter(raw_text: str) -> tuple[dict, str]:
    text = raw_text.lstrip("\ufeff")
    if not text.startswith("---"):
        raise ValueError("SKILL.md 必须以 YAML front matter 开始")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, flags=re.DOTALL)
    if match is None:
        raise ValueError("YAML front matter 未正确闭合")
    metadata = yaml.safe_load(match.group(1)) or {}
    if not isinstance(metadata, dict):
        raise ValueError("front matter 必须解析为对象")
    return metadata, match.group(2)


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cjk_count = sum(1 for character in text if "\u4e00" <= character <= "\u9fff")
    other_count = len(text) - cjk_count
    return max(1, cjk_count // 2 + other_count // 4)
