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
  it("enables the workspace only after loading console.v1", async () => {
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
      if (url.includes("/console/conversations/")) {
        return jsonResponse(emptyConversation());
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { state, wrapper } = mountConsole();
    await flushPromises();

    expect(state.compatibilityStatus.value).toBe("compatible");
    expect(state.isConsoleCompatible.value).toBe(true);
    expect(state.consoleConfig.value?.backend_version).toBe("v3.12.1");
    expect(fetchMock).toHaveBeenCalledTimes(4);
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
      collections: true,
    },
    endpoints: {
      ask: "/agent/ask",
      stream: "/agent/ask/stream",
      conversation: "/console/conversations/{conversation_id}",
      runs: "/runs",
    },
    default_memory_window: 3,
  };
}

function emptyConversation() {
  return {
    conversation_id: "conv_web_test",
    memory_snapshot: {
      conversation_id: "conv_web_test",
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
