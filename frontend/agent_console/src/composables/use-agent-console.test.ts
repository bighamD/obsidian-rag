import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, nextTick, watchEffect } from "vue";

import {
  applyAnswerDelta,
  applyProgressEvent,
  applyReasoningDelta,
  buildAgentAskPayload,
  createStreamingAssistantDraft,
  markStreamError,
  reconcileAssistantMessage,
  useAgentConsole,
} from "@/composables/use-agent-console";
import type { AgentOptions, AgentStreamEvent, ConsoleMessage, ProductionAskResponse } from "@/types/production";


const options: AgentOptions = {
  collection: "recipes",
  memoryWindow: 3,
  memoryCompactionEnabled: true,
  memoryCompactionTriggerTurns: 4,
  memoryCompactionTriggerTokens: 3000,
  topK: 5,
  mode: "hybrid",
  maxSteps: 4,
  maxRetries: 1,
  contextMaxChunks: 4,
  contextTokenBudget: 4000,
};

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Console contract startup", () => {
  it("loads server conversations and ignores obsolete localStorage sessions", async () => {
    localStorage.setItem("obsidian-rag.console.v1.sessions", JSON.stringify([
      { id: "conv_obsolete", title: "本地旧会话", updatedAt: "2026-01-01", messages: [] },
    ]));
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/console/config")) {
        return jsonResponse(consoleManifest());
      }
      if (url.endsWith("/health")) {
        return jsonResponse({ status: "ok", version: "v3.12.1" });
      }
      if (url.includes("/runs?")) {
        return jsonResponse([]);
      }
      if (url.includes("/console/conversations?")) {
        return jsonResponse(conversationList([conversationSummary("conv_server", "服务端会话")]));
      }
      if (url.includes("/console/conversations/")) {
        return jsonResponse(emptyConversation("conv_server"));
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { state, wrapper } = mountConsole();
    await flushPromises();

    expect(state.compatibilityStatus.value).toBe("compatible");
    expect(state.isConsoleCompatible.value).toBe(true);
    expect(state.consoleConfig.value?.backend_version).toBe("v3.12.1");
    expect(state.sessions.value.map((session) => session.id)).toEqual(["conv_server"]);
    expect(state.sessions.value[0].persisted).toBe(true);
    expect(state.activeConversationId.value).toBe("conv_server");
    expect(fetchMock).toHaveBeenCalledTimes(5);
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes("window=20"))).toBe(true);
    wrapper.unmount();
  });

  it("stops after an incompatible manifest without requesting workspace data", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ ...consoleManifest(), contract_version: "console.v0" }));
    vi.stubGlobal("fetch", fetchMock);

    const { state, wrapper } = mountConsole();
    await flushPromises();

    expect(state.compatibilityStatus.value).toBe("incompatible");
    expect(state.isConsoleCompatible.value).toBe(false);
    expect(state.compatibilityError.value).toContain("需要 console.v1");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("creates a temporary session without calling the backend", async () => {
    const fetchMock = workspaceFetchMock([conversationSummary("conv_server", "服务端会话")]);
    vi.stubGlobal("fetch", fetchMock);
    const { state, wrapper } = mountConsole();
    await flushPromises();
    const initialCallCount = fetchMock.mock.calls.length;

    state.createConversation();

    expect(state.activeSession.value.persisted).toBe(false);
    expect(state.activeSession.value.title).toBe("新会话");
    expect(fetchMock).toHaveBeenCalledTimes(initialCallCount);
    wrapper.unmount();
  });

  it("deletes the active persisted conversation and selects the next one", async () => {
    const fetchMock = workspaceFetchMock([
      conversationSummary("conv_delete", "待删除会话"),
      conversationSummary("conv_keep", "保留会话"),
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const { state, wrapper } = mountConsole();
    await flushPromises();

    await state.deleteConversation("conv_delete");

    expect(state.sessions.value.map((session) => session.id)).toEqual(["conv_keep"]);
    expect(state.activeConversationId.value).toBe("conv_keep");
    expect(fetchMock.mock.calls.some(([input, init]) => (
      String(input).endsWith("/console/conversations/conv_delete") && init?.method === "DELETE"
    ))).toBe(true);
    wrapper.unmount();
  });

  it("keeps the session when deletion fails", async () => {
    const fetchMock = workspaceFetchMock([conversationSummary("conv_keep", "保留会话")], {
      deleteStatus: 500,
    });
    vi.stubGlobal("fetch", fetchMock);
    const { state, wrapper } = mountConsole();
    await flushPromises();

    await state.deleteConversation("conv_keep");

    expect(state.sessions.value.map((session) => session.id)).toEqual(["conv_keep"]);
    expect(state.requestError.value).toContain("删除失败");
    wrapper.unmount();
  });
});


describe("buildAgentAskPayload", () => {
  it("forwards the selected collection", () => {
    const payload = buildAgentAskPayload("番茄炒蛋怎么做？", "conv_test", options);

    expect(payload.collection).toBe("recipes");
  });

  it("uses null when collection is blank", () => {
    const payload = buildAgentAskPayload("自动选择知识库", "conv_test", {
      ...options,
      collection: "  ",
    });

    expect(payload.collection).toBeNull();
  });
});

describe("answer delta", () => {
  const message = (): ConsoleMessage => ({
    id: "draft",
    role: "assistant",
    text: "",
    createdAt: "2026-07-15T00:00:00Z",
    isStreaming: true,
    streamSequence: 0,
  });

  const event = (sequence: number, delta: string): AgentStreamEvent => ({
    event_id: sequence,
    run_id: "run_test",
    name: "answer_delta",
    status: "running",
    occurred_at: "2026-07-15T00:00:00Z",
    detail: "delta",
    data: { message_id: "msg_test", sequence, delta },
  });

  it("appends ordered deltas and ignores duplicates", () => {
    const draft = message();

    applyProgressEvent(draft, {
      ...event(1, ""),
      name: "progress",
      data: {
        agent: {
          phase: "retrieval",
          status: "running",
          collection: "food_safety",
        },
      },
    });

    expect(applyAnswerDelta(draft, event(1, "剩菜"))).toBe(true);
    expect(applyAnswerDelta(draft, event(1, "重复"))).toBe(false);
    expect(applyAnswerDelta(draft, event(2, "冷藏三天"))).toBe(true);
    expect(draft.text).toBe("剩菜冷藏三天");
    expect(draft.currentProgress).toBe("正在生成回答…");
  });

  it("maps progress facts without writing them into answer text", () => {
    const draft = message();
    const applied = applyProgressEvent(draft, {
      ...event(7, ""),
      name: "progress",
      data: {
        agent: {
          phase: "retrieval",
          status: "completed",
          collection: "food_safety",
          result_count: 4,
        },
      },
    });

    expect(applied).toBe(true);
    expect(draft.currentProgress).toBe("已找到 4 条资料，正在检查证据…");
    expect(draft.text).toBe("");
  });

  it("appends reasoning with an independent sequence and keeps answer isolated", () => {
    const draft = message();
    draft.reasoningSequence = 0;
    draft.reasoningText = "";

    expect(applyReasoningDelta(draft, { ...event(1, "先分析。"), name: "reasoning_delta" })).toBe(true);
    expect(applyReasoningDelta(draft, { ...event(1, "重复"), name: "reasoning_delta" })).toBe(false);
    expect(applyAnswerDelta(draft, event(1, "最终答案"))).toBe(true);
    expect(applyReasoningDelta(draft, { ...event(2, "再检查。"), name: "reasoning_delta" })).toBe(true);

    expect(draft.reasoningText).toBe("先分析。再检查。");
    expect(draft.text).toBe("最终答案");
    expect(draft.reasoningSequence).toBe(2);
    expect(draft.streamSequence).toBe(1);
  });

  it("creates a reactive draft so progress changes trigger the transcript", async () => {
    const draft = createStreamingAssistantDraft();
    let observedProgress = "";
    watchEffect(() => {
      observedProgress = draft.currentProgress ?? "";
    });

    applyProgressEvent(draft, {
      ...event(8, ""),
      name: "progress",
      data: {
        agent: {
          phase: "planning",
          status: "running",
        },
      },
    });
    await nextTick();

    expect(observedProgress).toBe("正在生成执行计划…");
  });

  it("uses the final response as authoritative text without adding another message", () => {
    const draft = message();
    draft.reasoningText = "学习调试 reasoning";
    applyAnswerDelta(draft, event(1, "部分"));
    const result = {
      run: {
        timing: { duration_ms: 3200 },
        metrics: { retrieval_result_count: 4 },
      },
      agent_response: {
        answer: "完整答案",
        sources: ["food.md"],
        collection: "food_safety",
        answer_stream: { llm_ttft_ms: 620 },
        memory_write: { saved: true },
      },
    } as ProductionAskResponse;

    reconcileAssistantMessage(draft, result);

    expect(draft.text).toBe("完整答案");
    expect(draft.sources).toEqual(["food.md"]);
    expect(draft.isStreaming).toBe(false);
    expect(draft.reasoningText).toBe("学习调试 reasoning");
    expect(draft.summary).toEqual({
      collection: "food_safety",
      retrievalResultCount: 4,
      durationMs: 3200,
      ttftMs: 620,
      memorySaved: true,
    });
  });

  it("keeps partial visible text when the stream is interrupted", () => {
    const draft = message();
    applyAnswerDelta(draft, event(1, "已收到的部分答案"));

    markStreamError(draft, "连接中断");

    expect(draft.text).toBe("已收到的部分答案");
    expect(draft.streamError).toBe("连接中断");
    expect(draft.isStreaming).toBe(false);
  });
});

function mountConsole() {
  let state!: ReturnType<typeof useAgentConsole>;
  const wrapper = mount(defineComponent({
    setup() {
      state = useAgentConsole();
      return () => h("div");
    },
  }));
  return { state, wrapper };
}

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function consoleManifest() {
  return {
    contract_version: "console.v1",
    backend_version: "v3.12.1",
    features: {
      json: true,
      sse: true,
      answer_delta: true,
      reasoning_delta: true,
      conversation_memory: true,
      conversation_management: true,
      collections: true,
    },
    endpoints: {
      ask: "/agent/ask",
      stream: "/agent/ask/stream",
      conversations: "/console/conversations",
      conversation: "/console/conversations/{conversation_id}",
      runs: "/runs",
    },
    default_memory_window: 3,
  };
}

function emptyConversation(conversationId: string) {
  return {
    conversation_id: conversationId,
    memory_snapshot: {
      conversation_id: conversationId,
      window: 3,
      recent_turns: [],
      total_turn_count: 0,
      loaded_turn_count: 0,
      omitted_turn_count: 0,
      summary_text: "",
      summary_through_turn_id: null,
      summary_updated_at: null,
    },
  };
}

function conversationSummary(conversationId: string, title: string) {
  return {
    conversation_id: conversationId,
    title,
    turn_count: 1,
    created_at: "26-07-16 20:00:00",
    updated_at: "26-07-16 21:00:00",
  };
}

function conversationList(conversations: ReturnType<typeof conversationSummary>[]) {
  return { conversations };
}

function workspaceFetchMock(
  conversations: ReturnType<typeof conversationSummary>[],
  options: { deleteStatus?: number } = {},
) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/console/config")) {
      return jsonResponse(consoleManifest());
    }
    if (url.endsWith("/health")) {
      return jsonResponse({ status: "ok", version: "v3.12.1" });
    }
    if (url.includes("/runs?")) {
      return jsonResponse([]);
    }
    if (url.includes("/console/conversations?")) {
      return jsonResponse(conversationList(conversations));
    }
    if (init?.method === "DELETE" && url.includes("/console/conversations/")) {
      if (options.deleteStatus && options.deleteStatus >= 400) {
        return new Response(JSON.stringify({ detail: "删除失败" }), {
          status: options.deleteStatus,
          headers: { "Content-Type": "application/json" },
        });
      }
      return jsonResponse({
        conversation_id: url.split("/").pop(),
        deleted: true,
        deleted_turn_count: 1,
      });
    }
    if (url.includes("/console/conversations/")) {
      return jsonResponse(emptyConversation(url.split("/").pop()?.split("?")[0] ?? "conv_test"));
    }
    throw new Error(`Unexpected request: ${url}`);
  });
}
