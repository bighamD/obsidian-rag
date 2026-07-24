from __future__ import annotations

from threading import Lock

from obsidian_rag.core.permissions.schemas import PermissionAuditRecord


class InMemoryPermissionAuditStore:
    """V3.13 学习版线程安全审计 Store；进程重启后记录会丢失。"""

    def __init__(self, max_records: int = 200):
        self.max_records = max_records
        self._records: list[PermissionAuditRecord] = []
        self._lock = Lock()

    def append(self, record: PermissionAuditRecord) -> None:
        with self._lock:
            self._records = [record, *self._records][: self.max_records]

    def list_records(self, limit: int = 50) -> list[PermissionAuditRecord]:
        with self._lock:
            return list(self._records[:limit])
