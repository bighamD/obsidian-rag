<script setup lang="ts">
import { Bot, ChevronDown, Database, Download, FileText, MessageSquare, Wrench } from "lucide-vue-next";

import type { DeepAgentNativeResponse } from "@/types/production";
import { formatDuration } from "@/utils/format";

defineProps<{
  response: DeepAgentNativeResponse;
}>();

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
.deep-agent-panel, .deep-agent-events, .deep-agent-messages, .deep-agent-artifacts { display: grid; gap: 10px; }
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
</style>

