<script setup lang="ts">
import { Bot, CircleAlert, LoaderCircle, UserRound } from "lucide-vue-next";
import { nextTick, ref, watch } from "vue";

import type { ConsoleMessage } from "@/types/production";
import { formatDateTime, renderSafeMarkdown } from "@/utils/format";

const props = defineProps<{
  isRunning: boolean;
  messages: ConsoleMessage[];
}>();

const scrollContainer = ref<HTMLElement | null>(null);

watch(
  () => [props.messages.length, props.isRunning],
  async () => {
    await nextTick();
    scrollContainer.value?.scrollTo({ top: scrollContainer.value.scrollHeight, behavior: "smooth" });
  },
);
</script>

<template>
  <main ref="scrollContainer" class="chat-transcript" aria-label="Agent 对话">
    <div v-if="!messages.length && !isRunning" class="empty-chat-state">
      <Bot :size="28" />
      <p>开始一段知识库对话</p>
    </div>

    <article v-for="message in messages" :key="message.id" class="message" :class="message.role">
      <div class="message-avatar" aria-hidden="true">
        <UserRound v-if="message.role === 'user'" :size="17" />
        <CircleAlert v-else-if="message.role === 'error'" :size="17" />
        <Bot v-else :size="17" />
      </div>
      <div class="message-body">
        <div class="message-meta">
          <strong>{{ message.role === 'user' ? '你' : message.role === 'error' ? '运行错误' : 'Obsidian RAG' }}</strong>
          <time>{{ formatDateTime(message.createdAt) }}</time>
        </div>
        <div v-if="message.role === 'assistant'" class="message-content markdown" v-html="renderSafeMarkdown(message.text)" />
        <p v-else class="message-content">{{ message.text }}</p>
        <div v-if="message.sources?.length" class="source-row">
          <span v-for="source in message.sources" :key="source" class="source-chip">{{ source }}</span>
        </div>
      </div>
    </article>

    <article v-if="isRunning" class="message assistant running-message">
      <div class="message-avatar" aria-hidden="true"><LoaderCircle :size="17" class="spin" /></div>
      <div class="message-body">
        <div class="message-meta"><strong>Obsidian RAG</strong></div>
        <p class="message-content">正在运行 Agent</p>
      </div>
    </article>
  </main>
</template>
