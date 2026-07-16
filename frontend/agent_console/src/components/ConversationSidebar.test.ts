import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ConversationSidebar from "@/components/ConversationSidebar.vue";
import type { ConsoleSession } from "@/types/production";


const sessions: ConsoleSession[] = [
  {
    id: "conv_test",
    title: "服务端会话",
    updatedAt: "26-07-16 21:00:00",
    persisted: true,
    messages: [],
  },
];


describe("ConversationSidebar", () => {
  it("emits delete without selecting the conversation", async () => {
    const wrapper = mount(ConversationSidebar, {
      props: {
        activeConversationId: "conv_test",
        apiOnline: true,
        deletingConversationId: null,
        isRunning: false,
        recentRuns: [],
        sessions,
      },
    });

    await wrapper.get('[aria-label="删除会话 服务端会话"]').trigger("click");

    expect(wrapper.emitted("delete")).toEqual([["conv_test"]]);
    expect(wrapper.emitted("select")).toBeUndefined();
  });

  it("disables delete while an Agent request is running", () => {
    const wrapper = mount(ConversationSidebar, {
      props: {
        activeConversationId: "conv_test",
        apiOnline: true,
        deletingConversationId: null,
        isRunning: true,
        recentRuns: [],
        sessions,
      },
    });

    expect(wrapper.get('[aria-label="删除会话 服务端会话"]').attributes("disabled")).toBeDefined();
  });
});
