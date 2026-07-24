from types import SimpleNamespace

from obsidian_rag.core.llm import ChatStreamDelta
from obsidian_rag.llm import OpenAIChatClient


class FakeCompletions:
    def __init__(self, deltas):
        self.deltas = deltas
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return [
            SimpleNamespace(
                choices=[SimpleNamespace(delta=FakeDelta(delta))]
            )
            for delta in self.deltas
        ]


class FakeDelta:
    def __init__(self, data):
        self.data = data

    def model_dump(self, exclude_none=True):
        return self.data


def _client(*, enabled: bool, deltas):
    client = object.__new__(OpenAIChatClient)
    client.model = "gpt-5.4-mini"
    client.reasoning_stream_enabled = enabled
    client.reasoning_effort = "medium"
    completions = FakeCompletions(deltas)
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return client, completions


def test_chat_client_maps_cpa_reasoning_and_content_when_enabled():
    client, completions = _client(
        enabled=True,
        deltas=[{"reasoning_content": "先列方程。"}, {"content": "答案是 4。"}],
    )

    chunks = list(client.stream([{"role": "user", "content": "2+2"}]))

    assert chunks == [
        ChatStreamDelta(kind="reasoning", text="先列方程。"),
        ChatStreamDelta(kind="content", text="答案是 4。"),
    ]
    assert completions.request["reasoning_effort"] == "medium"


def test_chat_client_omits_reasoning_request_and_output_when_disabled():
    client, completions = _client(
        enabled=False,
        deltas=[{"reasoning_content": "不应暴露"}, {"content": "答案"}],
    )

    chunks = list(client.stream([{"role": "user", "content": "问题"}]))

    assert chunks == [ChatStreamDelta(kind="content", text="答案")]
    assert "reasoning_effort" not in completions.request
