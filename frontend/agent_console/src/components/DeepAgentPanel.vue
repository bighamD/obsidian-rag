<script setup lang="ts">
import { Bot, Brain, ChevronDown, Database, Download, FileText, History, Pencil, Plus, Save, Trash2, Wrench, MessageSquare } from "lucide-vue-next";
import { ref, watch } from "vue";

import { deleteLongTermMemory, fetchMemoryAudits, putLongTermMemory } from "@/api/production-client";
import type { DeepAgentNativeResponse, LongTermMemoryItem, LongTermMemoryKind, MemoryAuditRecord } from "@/types/production";
import { formatDuration } from "@/utils/format";

const props = defineProps<{
  response: DeepAgentNativeResponse;
}>();

const memories = ref<LongTermMemoryItem[]>([]);
const audits = ref<MemoryAuditRecord[]>([]);
const editingId = ref<string | null>(null);
const draftKind = ref<LongTermMemoryKind>("preference");
const draftContent = ref("");
const memoryBusy = ref(false);
const memoryError = ref("");

watch(
  () => props.response.durable_context,
  async (context) => {
    memories.value = [...(context?.long_term_memories ?? [])];
    if (context) {
      try {
        audits.value = await fetchMemoryAudits();
      } catch {
        audits.value = [];
      }
    }
  },
  { immediate: true },
);

const apiBase = import.meta.env.VITE_API_BASE ?? "/api";

function json(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? "null";
  } catch {
    return String(value ?? "null");
  }
}

function artifactUrl(path: string): string {
  return `${apiBase}${path}`;
}

function editMemory(item: LongTermMemoryItem): void {
  editingId.value = item.memory_id;
  draftKind.value = item.kind;
  draftContent.value = item.content;
  memoryError.value = "";
}

function resetMemoryForm(): void {
  editingId.value = null;
  draftKind.value = "preference";
  draftContent.value = "";
  memoryError.value = "";
}

async function saveMemory(): Promise<void> {
  const content = draftContent.value.trim();
  if (!content || memoryBusy.value) return;
  memoryBusy.value = true;
  memoryError.value = "";
  try {
    const saved = await putLongTermMemory({
      memory_id: editingId.value ?? undefined,
      kind: draftKind.value,
      content,
      reason: "Agent Console 手动维护",
    });
    memories.value = [saved, ...memories.value.filter((item) => item.memory_id !== saved.memory_id)];
    audits.value = await fetchMemoryAudits();
    resetMemoryForm();
  } catch (error) {
    memoryError.value = error instanceof Error ? error.message : "保存 Memory 失败";
  } finally {
    memoryBusy.value = false;
  }
}

async function removeMemory(memoryId: string): Promise<void> {
  if (memoryBusy.value) return;
  memoryBusy.value = true;
  memoryError.value = "";
  try {
    if (await deleteLongTermMemory(memoryId)) {
      memories.value = memories.value.filter((item) => item.memory_id !== memoryId);
      audits.value = await fetchMemoryAudits();
    }
  } catch (error) {
    memoryError.value = error instanceof Error ? error.message : "删除 Memory 失败";
  } finally {
    memoryBusy.value = false;
  }
}
</script>

<template>
  <div class="deep-agent-panel">
    <div class="deep-agent-summary">
      <Bot :size="19" />
      <div>
        <strong>DeepAgents Tool Loop</strong>
        <p>{{ response.model_call_count }} 次模型调用 · {{ response.tool_calls.length }} 个 Tool Calls · {{ response.tool_messages.length }} 个 ToolMessages</p>
      </div>
      <span :class="['deep-agent-status', response.status]">{{ response.status }}</span>
    </div>

    <div v-if="response.selected_collections.length" class="collection-row">
      <Database :size="15" /><span>Collections</span><code>{{ response.selected_collections.join(', ') }}</code>
    </div>

    <section v-if="response.durable_context" class="durable-context-panel">
      <div class="durable-heading">
        <Brain :size="17" />
        <div>
          <strong>Durable Memory & Context</strong>
          <p><code>{{ response.durable_context.thread_id }}</code> · Run {{ response.run_id }}</p>
        </div>
      </div>

      <div class="context-metrics">
        <span><strong>{{ response.durable_context.thread_message_count }}</strong> 原始 messages</span>
        <span><strong>{{ response.durable_context.estimated_message_tokens }}</strong> 估算 tokens</span>
        <span><strong>{{ Math.round(response.durable_context.summary_trigger_fraction * 100) }}%</strong> Summary 阈值</span>
      </div>

      <details class="summary-details" :open="response.durable_context.summary.triggered">
        <summary><History :size="15" /><strong>Context Summary</strong><span>{{ response.durable_context.summary.triggered ? '已触发' : '未触发' }}</span><ChevronDown :size="15" /></summary>
        <div class="summary-body">
          <p v-if="response.durable_context.summary.summary_text">{{ response.durable_context.summary.summary_text }}</p>
          <p v-else>当前 Context 尚未达到模型 Profile 的压缩阈值。</p>
          <code v-if="response.durable_context.summary.history_file_path">{{ response.durable_context.summary.history_file_path }}</code>
          <small>该区域是可验证的 `_summarization_event` 投影，不是精确 Wire Prompt。</small>
        </div>
      </details>

      <div class="memory-manager">
        <div class="memory-manager-title"><strong>Long-term Memory</strong><code>{{ response.durable_context.memory_profile_path }}</code></div>
        <div class="memory-editor">
          <select v-model="draftKind" aria-label="Memory 类型">
            <option value="preference">preference</option>
            <option value="fact">fact</option>
            <option value="decision">decision</option>
          </select>
          <textarea v-model="draftContent" rows="3" placeholder="仅保存稳定偏好、长期事实或确认后的决策" />
          <div>
            <button type="button" :disabled="memoryBusy || !draftContent.trim()" title="保存 Memory" @click="saveMemory"><Save :size="14" />{{ editingId ? '更新' : '保存' }}</button>
            <button v-if="editingId" type="button" title="取消编辑" @click="resetMemoryForm">取消</button>
          </div>
          <p v-if="memoryError" class="memory-error">{{ memoryError }}</p>
        </div>
        <div v-if="memories.length" class="memory-list">
          <article v-for="item in memories" :key="item.memory_id">
            <span>{{ item.kind }}</span>
            <p>{{ item.content }}</p>
            <code>{{ item.memory_id }}</code>
            <div>
              <button type="button" title="编辑 Memory" @click="editMemory(item)"><Pencil :size="13" /></button>
              <button type="button" title="删除 Memory" @click="removeMemory(item.memory_id)"><Trash2 :size="13" /></button>
            </div>
          </article>
        </div>
        <button v-else type="button" class="empty-memory" title="新增 Memory" @click="resetMemoryForm"><Plus :size="14" />暂无长期 Memory</button>
      </div>

      <details v-if="audits.length" class="audit-details">
        <summary><History :size="15" /><strong>Memory Audit</strong><span>{{ audits.length }} 条</span><ChevronDown :size="15" /></summary>
        <ol>
          <li v-for="audit in audits" :key="audit.audit_id"><code>{{ audit.operation }}</code><span>{{ audit.summary }}</span><small>{{ audit.created_at }}</small></li>
        </ol>
      </details>
    </section>

    <div class="deep-agent-events">
      <p class="section-kicker">公开执行事件</p>
      <ol>
        <li v-for="event in response.execution_events" :key="event.sequence">
          <span>{{ event.sequence }}</span>
          <div><strong>{{ event.event_type }}</strong><p>{{ event.detail }}</p><small>{{ event.node_name || '-' }}<template v-if="event.duration_ms !== null"> · {{ formatDuration(event.duration_ms) }}</template></small></div>
        </li>
      </ol>
    </div>

    <div class="deep-agent-messages">
      <p class="section-kicker">Messages / Observation 数据流</p>
      <details v-for="message in response.messages" :key="`${message.sequence}-${message.message_id}`" :open="message.role === 'tool'">
        <summary>
          <MessageSquare v-if="message.role !== 'tool'" :size="15" />
          <Wrench v-else :size="15" />
          <strong>#{{ message.sequence }} {{ message.role }}</strong>
          <span v-if="message.tool_name">{{ message.tool_name }}</span>
          <span v-else-if="message.tool_calls.length">{{ message.tool_calls.map((call) => call.name).join(', ') }}</span>
          <ChevronDown :size="15" />
        </summary>
        <pre>{{ json(message.content) }}</pre>
        <div v-if="message.tool_calls.length" class="message-tool-calls">
          <article v-for="call in message.tool_calls" :key="call.call_id">
            <div><strong>{{ call.name }}</strong><span :class="['tool-status', call.status]">{{ call.status }}</span></div>
            <small>model call #{{ call.model_call_index }} · {{ call.call_id }}</small>
            <pre>{{ json(call.arguments) }}</pre>
          </article>
        </div>
      </details>
    </div>

    <div v-if="response.artifacts.length" class="deep-agent-artifacts">
      <p class="section-kicker">Artifacts</p>
      <article v-for="artifact in response.artifacts" :key="artifact.artifact_id">
        <FileText :size="16" />
        <div><strong>{{ artifact.relative_path }}</strong><span>{{ artifact.mime_type }} · {{ artifact.size_bytes }} bytes</span><code>{{ artifact.sha256.slice(0, 16) }}</code></div>
        <a :href="artifactUrl(artifact.download_url)" :download="artifact.relative_path" title="下载 Artifact"><Download :size="16" /></a>
      </article>
    </div>
  </div>
</template>

<style scoped>
.deep-agent-panel, .deep-agent-events, .deep-agent-messages, .deep-agent-artifacts, .durable-context-panel { display: grid; gap: 10px; }
.deep-agent-summary { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 9px; align-items: start; padding: 11px; color: #285b63; background: #eaf6f6; border: 1px solid #c8e6e6; border-radius: 6px; }
.deep-agent-summary strong, .deep-agent-events strong, .deep-agent-messages strong, .deep-agent-artifacts strong { color: #2c4358; font-size: 11px; }
.deep-agent-summary p, .deep-agent-events p { margin: 3px 0 0; color: #68788a; font-size: 10px; line-height: 1.45; }
.deep-agent-status, .tool-status { padding: 2px 6px; border-radius: 3px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 9px; white-space: nowrap; }
.deep-agent-status.succeeded, .tool-status.success { color: #087255; background: #def3e9; }
.deep-agent-status.waiting_for_approval, .tool-status.waiting_for_approval, .tool-status.requested { color: #956000; background: #fff0c7; }
.tool-status.failed, .tool-status.rejected { color: #b73535; background: #fee5e5; }
.collection-row { display: grid; grid-template-columns: auto auto minmax(0, 1fr); gap: 7px; align-items: center; color: #52677b; font-size: 10px; }
.collection-row code { overflow-wrap: anywhere; }
.deep-agent-events ol { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.deep-agent-events li { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 7px; padding: 8px; border: 1px solid #dce5e9; border-radius: 5px; }
.deep-agent-events li > span { display: grid; place-items: center; width: 22px; height: 22px; color: #fff; background: #397d99; border-radius: 50%; font-size: 9px; }
.deep-agent-events small, .deep-agent-messages summary span, .deep-agent-messages small, .deep-agent-artifacts span, .deep-agent-artifacts code { color: #7a8797; font-size: 9px; }
.deep-agent-messages details { overflow: hidden; background: #fff; border: 1px solid #dce5e9; border-radius: 5px; }
.deep-agent-messages summary { display: grid; grid-template-columns: auto auto minmax(0, 1fr) auto; gap: 7px; align-items: center; padding: 9px; cursor: pointer; list-style: none; }
.deep-agent-messages summary::-webkit-details-marker { display: none; }
.deep-agent-messages details[open] summary .lucide-chevron-down { transform: rotate(180deg); }
.deep-agent-messages pre, .message-tool-calls pre { max-height: 360px; overflow: auto; margin: 0; padding: 9px; color: #d6e7f4; background: #10263b; border-top: 1px solid #274258; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 9px; line-height: 1.5; white-space: pre-wrap; overflow-wrap: anywhere; }
.message-tool-calls { display: grid; gap: 7px; padding: 8px; background: #f5f8fa; }
.message-tool-calls article { overflow: hidden; border: 1px solid #dce5e9; border-radius: 5px; background: #fff; }
.message-tool-calls article > div { display: flex; justify-content: space-between; gap: 8px; padding: 8px 8px 0; }
.message-tool-calls small { display: block; padding: 3px 8px 8px; overflow-wrap: anywhere; }
.deep-agent-artifacts article { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 8px; align-items: start; padding: 9px; border: 1px solid #dce5e9; border-radius: 5px; }
.deep-agent-artifacts article div { display: grid; min-width: 0; gap: 2px; }
.deep-agent-artifacts a { color: #2478a8; }
.durable-context-panel { padding: 10px; border: 1px solid #cbdde5; border-radius: 6px; background: #f8fbfc; }
.durable-heading { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px; color: #285b63; }
.durable-heading p, .summary-body p { margin: 3px 0 0; color: #66798a; font-size: 10px; line-height: 1.5; white-space: pre-wrap; }
.durable-heading code, .memory-manager-title code, .summary-body code { color: #557082; font-size: 9px; overflow-wrap: anywhere; }
.context-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
.context-metrics span { padding: 7px; border: 1px solid #d9e6eb; border-radius: 4px; color: #6c7b89; background: #fff; font-size: 9px; }
.context-metrics strong { display: block; color: #2d6174; font-size: 12px; }
.summary-details, .audit-details { overflow: hidden; border: 1px solid #d9e6eb; border-radius: 5px; background: #fff; }
.summary-details summary, .audit-details summary { display: grid; grid-template-columns: auto auto minmax(0, 1fr) auto; gap: 7px; align-items: center; padding: 8px; cursor: pointer; list-style: none; font-size: 10px; }
.summary-details summary span, .audit-details summary span { color: #738493; text-align: right; }
.summary-body { display: grid; gap: 6px; padding: 9px; border-top: 1px solid #e2eaee; }
.summary-body small { color: #8795a1; font-size: 9px; }
.memory-manager { display: grid; gap: 7px; }
.memory-manager-title { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.memory-editor { display: grid; gap: 6px; padding: 8px; border: 1px solid #d9e6eb; border-radius: 5px; background: #fff; }
.memory-editor select, .memory-editor textarea { width: 100%; box-sizing: border-box; border: 1px solid #cbd8de; border-radius: 4px; padding: 6px; color: #344e60; background: #fff; font: inherit; font-size: 10px; }
.memory-editor textarea { resize: vertical; line-height: 1.5; }
.memory-editor > div, .memory-list article > div { display: flex; gap: 6px; justify-content: flex-end; }
.memory-editor button, .memory-list button, .empty-memory { display: inline-flex; align-items: center; gap: 4px; border: 1px solid #bfd1d9; border-radius: 4px; padding: 5px 7px; color: #315f70; background: #fff; cursor: pointer; font-size: 9px; }
.memory-editor button:disabled { opacity: .5; cursor: default; }
.memory-error { margin: 0; color: #b73535; font-size: 9px; }
.memory-list { display: grid; gap: 6px; }
.memory-list article { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 6px 8px; align-items: start; padding: 8px; border: 1px solid #d9e6eb; border-radius: 5px; background: #fff; }
.memory-list article > span { padding: 2px 5px; color: #17664f; background: #e0f2ea; border-radius: 3px; font-size: 8px; }
.memory-list p { margin: 0; color: #455d6d; font-size: 10px; line-height: 1.5; }
.memory-list code { grid-column: 2; color: #8a98a4; font-size: 8px; }
.memory-list article > div { grid-column: 3; grid-row: 1 / span 2; }
.empty-memory { justify-self: start; }
.audit-details ol { display: grid; gap: 5px; margin: 0; padding: 8px; border-top: 1px solid #e2eaee; list-style: none; }
.audit-details li { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 7px; font-size: 9px; }
.audit-details li code { color: #2b7187; }
.audit-details li span { color: #506776; }
.audit-details li small { grid-column: 2; color: #8a98a4; }
@media (max-width: 720px) { .context-metrics { grid-template-columns: 1fr; } }
</style>
