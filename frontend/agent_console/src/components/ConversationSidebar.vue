<script setup lang="ts">
import { Activity, Plus, RefreshCw, Trash2 } from "lucide-vue-next";

import type { ConsoleSession, RunRecord } from "@/types/production";
import { formatDateTime, shortId, statusLabel } from "@/utils/format";

defineProps<{
  activeConversationId: string;
  apiOnline: boolean | null;
  deletingConversationId: string | null;
  isRunning: boolean;
  recentRuns: RunRecord[];
  sessions: ConsoleSession[];
}>();

defineEmits<{
  select: [conversationId: string];
  create: [];
  delete: [conversationId: string];
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
      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ active: session.id === activeConversationId }"
      >
        <button class="session-select" @click="$emit('select', session.id)">
          <span class="session-title">{{ session.title }}</span>
          <span class="session-meta">
            {{ session.persisted ? formatDateTime(session.updatedAt) : '尚未保存' }}
          </span>
        </button>
        <button
          class="session-delete"
          :disabled="isRunning || deletingConversationId !== null"
          :title="session.persisted ? '删除会话及关联 Turns' : '删除临时会话'"
          :aria-label="`删除会话 ${session.title}`"
          @click.stop="$emit('delete', session.id)"
        >
          <Trash2 :size="14" />
        </button>
      </div>
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
