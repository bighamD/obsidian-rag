<script setup lang="ts">
import { Cable, ChevronDown, CircleAlert, Server, Wrench } from "lucide-vue-next";
import { computed } from "vue";

import type {
  McpLiveToolEvent,
  McpRuntimeResponse,
  ToolObservation,
} from "@/types/production";

const props = defineProps<{
  runtime: McpRuntimeResponse | null;
  liveToolEvents: McpLiveToolEvent[];
  observations: ToolObservation[];
}>();

const connectedCount = computed(
  () => props.runtime?.servers.filter((server) => server.status === "connected").length ?? 0,
);

function json(value: unknown): string {
  return JSON.stringify(value, null, 2) ?? String(value ?? "null");
}
</script>

<template>
  <div class="mcp-runtime-panel">
    <div v-if="runtime" class="mcp-runtime-summary">
      <Cable :size="18" />
      <div>
        <strong>MCP Connection Manager</strong>
        <p>{{ connectedCount }} / {{ runtime.servers.length }} 个 Server 已连接 · {{ runtime.tools.length }} 个 Tools</p>
      </div>
      <span :class="['mcp-runtime-state', runtime.started ? 'connected' : 'failed']">
        {{ runtime.started ? 'running' : 'stopped' }}
      </span>
    </div>

    <div v-if="runtime?.servers.length" class="mcp-server-list">
      <p class="section-kicker">Server Sessions</p>
      <article v-for="server in runtime.servers" :key="server.name" class="mcp-server-row">
        <Server :size="16" />
        <div>
          <strong>{{ server.name }}</strong>
          <span>{{ server.transport }} · {{ server.protocol_version || '未协商协议' }}</span>
          <p>{{ server.description }}</p>
          <small>{{ server.tool_count }} tools · {{ server.call_count }} calls · {{ server.failure_count }} failures</small>
          <p v-if="server.last_error" class="mcp-error"><CircleAlert :size="12" />{{ server.last_error }}</p>
        </div>
        <span :class="['mcp-server-status', server.status]">{{ server.status }}</span>
      </article>
    </div>

    <div v-if="liveToolEvents.length" class="mcp-live-calls">
      <p class="section-kicker">Live Tool Calls</p>
      <div v-for="event in liveToolEvents" :key="`${event.stepId}-${event.toolName}`" class="mcp-live-row">
        <Wrench :size="15" />
        <div><strong>{{ event.toolName }}</strong><span>{{ event.stepId }} · {{ event.source }}</span></div>
        <span :class="['mcp-call-status', event.status]">{{ event.status }}</span>
      </div>
    </div>

    <div v-if="observations.length" class="mcp-observation-list">
      <p class="section-kicker">Tool Observations</p>
      <details v-for="item in observations" :key="`${item.step_id}-${item.tool_name}`" class="mcp-observation">
        <summary>
          <Wrench :size="15" />
          <div><strong>{{ item.tool_name }}</strong><span>{{ item.step_id }} · {{ item.source }}</span><p>{{ item.summary }}</p></div>
          <span :class="['mcp-call-status', item.status]">{{ item.status }}</span>
          <ChevronDown :size="15" />
        </summary>
        <pre>{{ json(item.data) }}</pre>
      </details>
    </div>

    <div v-if="runtime?.tools.length" class="mcp-tool-catalog">
      <p class="section-kicker">Planner Tool Catalog</p>
      <details v-for="tool in runtime.tools" :key="tool.namespaced_name" class="mcp-tool-definition">
        <summary><Wrench :size="14" /><strong>{{ tool.namespaced_name }}</strong><span>{{ tool.read_only ? 'read-only' : 'unspecified' }}</span><ChevronDown :size="14" /></summary>
        <p>{{ tool.description || '没有工具说明' }}</p>
        <pre>{{ json(tool.input_schema) }}</pre>
      </details>
    </div>

    <p v-if="!runtime && !liveToolEvents.length && !observations.length" class="muted-text">当前后端没有提供 MCP Runtime 数据</p>
  </div>
</template>

<style scoped>
.mcp-runtime-panel { display: grid; gap: 14px; }
.mcp-runtime-summary { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 10px; align-items: start; padding: 11px; color: #285b63; background: #eaf6f6; border: 1px solid #c8e6e6; border-radius: 6px; }
.mcp-runtime-summary strong, .mcp-server-row strong, .mcp-live-row strong, .mcp-observation strong, .mcp-tool-definition strong { color: #2c4358; font-size: 12px; }
.mcp-runtime-summary p, .mcp-server-row p, .mcp-observation p, .mcp-tool-definition p { margin: 3px 0 0; color: #68788a; font-size: 11px; line-height: 1.45; }
.mcp-runtime-state, .mcp-server-status, .mcp-call-status { padding: 2px 6px; border-radius: 3px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 9px; white-space: nowrap; }
.connected, .success { color: #087255; background: #def3e9; }
.connecting, .running { color: #956000; background: #fff0c7; }
.degraded { color: #995b14; background: #ffead2; }
.failed { color: #b73535; background: #fee5e5; }
.disconnected { color: #6f7d8d; background: #edf1f4; }
.skipped { color: #6f7d8d; background: #edf1f4; }
.mcp-server-list, .mcp-live-calls, .mcp-observation-list, .mcp-tool-catalog { display: grid; gap: 7px; }
.mcp-server-row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 8px; align-items: start; padding: 9px; background: #fff; border: 1px solid #dce5e9; border-radius: 5px; }
.mcp-server-row div { display: grid; min-width: 0; gap: 2px; }
.mcp-server-row span, .mcp-server-row small, .mcp-live-row span, .mcp-observation span { color: #7a8797; font-size: 10px; }
.mcp-server-row .mcp-server-status { color: inherit; }
.mcp-error { display: flex; align-items: flex-start; gap: 4px; color: #b43838 !important; overflow-wrap: anywhere; }
.mcp-live-row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 8px 9px; background: #fff; border: 1px solid #dce5e9; border-radius: 5px; }
.mcp-live-row div { display: grid; min-width: 0; gap: 2px; }
.mcp-observation, .mcp-tool-definition { overflow: hidden; background: #fff; border: 1px solid #dce5e9; border-radius: 5px; }
.mcp-observation summary { display: grid; grid-template-columns: auto minmax(0, 1fr) auto auto; gap: 8px; align-items: start; padding: 9px; cursor: pointer; list-style: none; }
.mcp-observation summary > div { min-width: 0; }
.mcp-observation summary p { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.mcp-observation pre, .mcp-tool-definition pre { max-height: 360px; overflow: auto; margin: 0; padding: 9px; color: #405267; background: #f7f9fa; border-top: 1px solid #e1e7ea; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 10px; line-height: 1.5; white-space: pre-wrap; overflow-wrap: anywhere; }
.mcp-tool-definition summary { display: grid; grid-template-columns: auto minmax(0, 1fr) auto auto; gap: 7px; align-items: center; padding: 8px 9px; cursor: pointer; list-style: none; }
.mcp-tool-definition > p { padding: 0 9px 8px; }
.mcp-observation summary::-webkit-details-marker, .mcp-tool-definition summary::-webkit-details-marker { display: none; }
.mcp-observation[open] .lucide-chevron-down, .mcp-tool-definition[open] .lucide-chevron-down { transform: rotate(180deg); }
.lucide-chevron-down { transition: transform 160ms ease; }
</style>
