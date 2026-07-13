<script setup lang="ts">
import { Bot, MessageSquarePlus, PanelRightOpen, RefreshCw } from "lucide-vue-next";
import { computed, ref } from "vue";

import ChatComposer from "@/components/ChatComposer.vue";
import ChatTranscript from "@/components/ChatTranscript.vue";
import ConversationSidebar from "@/components/ConversationSidebar.vue";
import RunInspector from "@/components/RunInspector.vue";
import { useAgentConsole } from "@/composables/use-agent-console";
import type { AgentOptions } from "@/types/production";

const consoleState = useAgentConsole();
const question = ref("");
const mobileInspectorOpen = ref(false);
const activeMessages = computed(() => consoleState.activeSession.value?.messages ?? []);

async function submitQuestion() {
  const value = question.value;
  question.value = "";
  await consoleState.submit(value);
}

async function selectConversation(conversationId: string) {
  mobileInspectorOpen.value = false;
  await consoleState.selectConversation(conversationId);
}

function updateOptions(value: AgentOptions) {
  Object.assign(consoleState.options, value);
}
</script>

<template>
  <div class="console-shell">
    <header class="app-header">
      <div class="brand-lockup"><span class="brand-mark"><Bot :size="20" /></span><div><strong>Obsidian RAG</strong><span>Agent Console · V3.10.1</span></div></div>
      <div class="header-actions">
        <button class="header-icon-button desktop-hidden" title="打开运行检查器" aria-label="打开运行检查器" @click="mobileInspectorOpen = true"><PanelRightOpen :size="19" /></button>
        <button class="header-icon-button" title="刷新工作区" aria-label="刷新工作区" @click="consoleState.refreshWorkspace"><RefreshCw :size="18" /></button>
        <button class="new-conversation-button" @click="consoleState.createConversation"><MessageSquarePlus :size="17" />新建会话</button>
      </div>
    </header>

    <div class="workspace-grid">
      <ConversationSidebar
        :active-conversation-id="consoleState.activeConversationId.value"
        :api-online="consoleState.apiOnline.value"
        :recent-runs="consoleState.recentRuns.value"
        :sessions="consoleState.sessions.value"
        @create="consoleState.createConversation"
        @refresh="consoleState.refreshWorkspace"
        @select="selectConversation"
      />

      <section class="chat-pane">
        <div class="conversation-bar">
          <div><p class="section-kicker">当前会话</p><strong>{{ consoleState.activeConversationId.value }}</strong></div>
          <span v-if="consoleState.requestError.value" class="inline-error">{{ consoleState.requestError.value }}</span>
        </div>
        <ChatTranscript :is-running="consoleState.isRunning.value" :messages="activeMessages" />
        <ChatComposer
          v-model="question"
          :options="consoleState.options"
          :is-running="consoleState.isRunning.value"
          @submit="submitQuestion"
          @update:options="updateOptions"
        />
      </section>

      <RunInspector
        class="desktop-inspector"
        :is-running="consoleState.isRunning.value"
        :memory-snapshot="consoleState.memorySnapshot.value"
        :response="consoleState.response.value"
      />
    </div>

    <div v-if="mobileInspectorOpen" class="mobile-inspector-layer">
      <button class="scrim" aria-label="关闭运行检查器" @click="mobileInspectorOpen = false" />
      <RunInspector
        class="mobile-inspector"
        :is-running="consoleState.isRunning.value"
        :memory-snapshot="consoleState.memorySnapshot.value"
        :response="consoleState.response.value"
      />
    </div>
  </div>
</template>
