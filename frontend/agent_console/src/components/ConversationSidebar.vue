<script setup lang="ts">
import { Activity, Plus, RefreshCw } from "lucide-vue-next";

import type { ConsoleSession, RunRecord } from "@/types/production";
import { formatDateTime, shortId, statusLabel } from "@/utils/format";

defineProps<{
  activeConversationId: string;
  apiOnline: boolean | null;
  recentRuns: RunRecord[];
  sessions: ConsoleSession[];
}>();

defineEmits<{
  select: [conversationId: string];
  create: [];
  refresh: [];
}>();
</script>

<template>
  <aside class="conversation-sidebar" aria-label="会话列表">
    <div class="sidebar-head">
      <div>
        <p class="section-kicker">会话</p>
        <h2>本地工作区</h2>
      </div>
      <button class="icon-button" title="新建会话" aria-label="新建会话" @click="$emit('create')">
        <Plus :size="18" />
      </button>
    </div>

    <nav class="session-list" aria-label="浏览器保存的会话">
      <button
        v-for="session in sessions"
        :key="session.id"
        class="session-row"
        :class="{ active: session.id === activeConversationId }"
        @click="$emit('select', session.id)"
      >
        <span class="session-title">{{ session.title }}</span>
        <span class="session-meta">{{ formatDateTime(session.updatedAt) }}</span>
      </button>
    </nav>

    <section class="run-list-section" aria-label="近期运行">
      <div class="section-row">
        <p class="section-kicker">近期运行</p>
        <button class="icon-button small" title="刷新运行记录" aria-label="刷新运行记录" @click="$emit('refresh')">
          <RefreshCw :size="15" />
        </button>
      </div>
      <div v-if="recentRuns.length" class="run-list">
        <div v-for="run in recentRuns" :key="run.run_id" class="run-row">
          <Activity :size="15" :class="`status-icon ${run.status}`" />
          <div>
            <span>{{ shortId(run.run_id) }}</span>
            <small>{{ statusLabel(run.status) }} · {{ formatDateTime(run.timing.started_at) }}</small>
          </div>
        </div>
      </div>
      <p v-else class="muted-text">暂无运行记录</p>
    </section>

    <div class="sidebar-footer">
      <span class="connection-dot" :class="apiOnline === true ? 'online' : apiOnline === false ? 'offline' : 'unknown'" />
      <span>{{ apiOnline === true ? 'API 已连接' : apiOnline === false ? 'API 未连接' : '正在检查 API' }}</span>
    </div>
  </aside>
</template>
