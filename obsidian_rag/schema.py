from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


Metadata = dict[str, Any]


@dataclass(frozen=True)
class TextChunk:
    text: str
    metadata: Metadata = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    chunk: TextChunk
    score: float
