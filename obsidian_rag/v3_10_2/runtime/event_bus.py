from __future__ import annotations

import json
from collections import defaultdict
from queue import Queue
from threading import RLock
from typing import Iterator

from obsidian_rag.v3_10.runtime.lifecycle import _now
from obsidian_rag.v3_10.schemas import RunStatus
from obsidian_rag.v3_10_2.schemas import AgentStreamEvent


# 收到终态事件后 iter_events 主动结束，SSE 连接随之关闭。
TERMINAL_EVENTS = {"run_succeeded", "run_failed"}


class RunEventBus:
    """单进程 Run 事件总线，供后台 Agent 线程和 SSE 响应之间传递事件。

    生产者（lifecycle._run 后台线程）通过 publish 写入 Queue；
    消费者（FastAPI StreamingResponse）通过 iter_sse 阻塞读取。
    每个 run_id 拥有独立队列，互不干扰。
    """

    def __init__(self):
        self._queues: dict[str, Queue[AgentStreamEvent]] = defaultdict(Queue)
        self._counters: dict[str, int] = defaultdict(int)
        # publish 与 create_run 可能并发，需要保护计数器和队列初始化。
        self._lock = RLock()

    def create_run(self, run_id: str) -> None:
        """为指定 Run 初始化事件队列和 event_id 计数器。"""

        with self._lock:
            # setdefault 避免重复创建时覆盖已有队列（队列中可能已有事件）。
            self._queues.setdefault(run_id, Queue())
            self._counters.setdefault(run_id, 0)

    def publish(
        self,
        run_id: str,
        name: str,
        status: RunStatus,
        detail: str,
        data: dict | None = None,
    ) -> AgentStreamEvent:
        """向指定 Run 发布一条事件，阻塞等待的消费者会立即收到。"""

        with self._lock:
            self.create_run(run_id)
            self._counters[run_id] += 1
            event = AgentStreamEvent(
                event_id=self._counters[run_id],
                run_id=run_id,
                name=name,
                status=status,
                occurred_at=_now(),
                detail=detail,
                data=data or {},
            )
            self._queues[run_id].put(event)
            return event

    def iter_events(self, run_id: str) -> Iterator[AgentStreamEvent]:
        """阻塞式消费指定 Run 的事件流，直到收到终态事件后结束。"""

        self.create_run(run_id)
        queue = self._queues[run_id]
        while True:
            # 队列为空时阻塞，直到后台线程 publish 新事件。
            event = queue.get()
            yield event
            if event.name in TERMINAL_EVENTS:
                return

    def iter_sse(self, run_id: str) -> Iterator[str]:
        """将事件流格式化为 SSE 文本帧，供 StreamingResponse 直接推送。"""

        for event in self.iter_events(run_id):
            payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
            yield f"id: {event.event_id}\nevent: {event.name}\ndata: {payload}\n\n"
