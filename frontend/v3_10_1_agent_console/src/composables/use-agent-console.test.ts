import { describe, expect, it } from "vitest";

import { buildAgentAskPayload } from "@/composables/use-agent-console";
import type { AgentOptions } from "@/types/production";


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
