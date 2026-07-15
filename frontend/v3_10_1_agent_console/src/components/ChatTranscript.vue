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
  () => [props.messages.length, props.isRunning, props.messages.at(-1)?.text],
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
        <div
          v-if="message.role === 'assistant' && message.text"
          class="message-content markdown"
          v-html="renderSafeMarkdown(message.text)"
        />
        <p v-else-if="message.role === 'assistant'" class="message-content">
          <LoaderCircle :size="15" class="spin" /> 正在生成回答…
        </p>
        <p v-else class="message-content">{{ message.text }}</p>
        <p v-if="message.streamError" class="message-content stream-error">流式连接中断：{{ message.streamError }}</p>
        <div v-if="message.sources?.length" class="source-row">
          <span v-for="source in message.sources" :key="source" class="source-chip">{{ source }}</span>
        </div>
      </div>
    </article>

  </main>
</template>
