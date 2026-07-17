from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol


class Reranker(Protocol):
    """模型 Provider 只负责为 query-document pairs 产生相关性分数。"""

    provider: str
    model: str | None
    device: str | None

    def score(self, query: str, documents: Sequence[str]) -> list[float]: ...


class FakeReranker:
    """离线测试用确定性 Provider；不会下载模型。"""

    provider = "fake"
    model = "deterministic-fake"
    device = "cpu"

    def __init__(self, scorer: Callable[[str, str], float] | None = None):
        self._scorer = scorer or (lambda query, document: float(document.lower().count(query.lower())))

    def score(self, query: str, documents: Sequence[str]) -> list[float]:
        return [float(self._scorer(query, document)) for document in documents]


class CrossEncoderReranker:
    """延迟加载 sentence-transformers CrossEncoder 的本地 Provider。"""

    provider = "sentence_transformers"

    def __init__(self, model: str, *, device: str = "auto", batch_size: int = 8):
        self.model = model
        self.device = device
        self.batch_size = batch_size
        self._client = None

    def score(self, query: str, documents: Sequence[str]) -> list[float]:
        if not documents:
            return []
        client = self._load()
        values = client.predict(
            [(query, document) for document in documents],
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        tolist = getattr(values, "tolist", None)
        raw = tolist() if callable(tolist) else list(values)
        return [float(value[0] if isinstance(value, list) else value) for value in raw]

    def _load(self):
        if self._client is not None:
            return self._client
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError("Reranker 依赖未安装，请执行 `pip install -e '.[rerank]'`") from exc
        kwargs = {} if self.device == "auto" else {"device": self.device}
        self._client = CrossEncoder(self.model, **kwargs)
        return self._client
