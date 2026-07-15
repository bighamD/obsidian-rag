import { describe, expect, it } from "vitest";

import {
  applyAnswerDelta,
  buildAgentAskPayload,
  markStreamError,
  reconcileAssistantMessage,
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

    expect(applyAnswerDelta(draft, event(1, "剩菜"))).toBe(true);
    expect(applyAnswerDelta(draft, event(1, "重复"))).toBe(false);
    expect(applyAnswerDelta(draft, event(2, "冷藏三天"))).toBe(true);
    expect(draft.text).toBe("剩菜冷藏三天");
  });

  it("uses the final response as authoritative text without adding another message", () => {
    const draft = message();
    applyAnswerDelta(draft, event(1, "部分"));
    const result = {
      run: {},
      agent_response: { answer: "完整答案", sources: ["food.md"] },
    } as ProductionAskResponse;

    reconcileAssistantMessage(draft, result);

    expect(draft.text).toBe("完整答案");
    expect(draft.sources).toEqual(["food.md"]);
    expect(draft.isStreaming).toBe(false);
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
