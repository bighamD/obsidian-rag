from __future__ import annotations

from collections import OrderedDict
from threading import RLock

from obsidian_rag.v3_10.schemas import RunRecord


class InMemoryRunStore:
    """线程安全的近期 Run Store。

    它只用于学习 Run Lifecycle 和单进程 Swagger 调试；重启进程会清空记录，
    也不适用于多进程部署。持久化 Run Store 留给后续版本。
    """

    def __init__(self, limit: int = 100):
        self.limit = max(1, limit)
        self._records: OrderedDict[str, RunRecord] = OrderedDict()
        self._lock = RLock()

    def save(self, record: RunRecord) -> RunRecord:
        with self._lock:
            self._records[record.run_id] = record.model_copy(deep=True)
            self._records.move_to_end(record.run_id)
            while len(self._records) > self.limit:
                self._records.popitem(last=False)
        return record

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            record = self._records.get(run_id)
            return record.model_copy(deep=True) if record else None

    def list_recent(self, limit: int = 20) -> list[RunRecord]:
        with self._lock:
            records = list(self._records.values())[-limit:]
            return [record.model_copy(deep=True) for record in reversed(records)]
