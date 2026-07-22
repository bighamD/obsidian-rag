<script setup lang="ts">
import { Box, CheckCircle2, Download, FileCode2, TerminalSquare, TriangleAlert } from "lucide-vue-next";

import type { ArtifactRecord, SandboxRuntimeConfigResponse, ToolObservation } from "@/types/production";

defineProps<{
  runtime: SandboxRuntimeConfigResponse | null;
  workspaceId: string | null;
  artifacts: ArtifactRecord[];
  observations: ToolObservation[];
}>();

const apiBase = import.meta.env.VITE_API_BASE ?? "/api";

function downloadUrl(artifact: ArtifactRecord): string {
  return `${apiBase}/sandbox/artifacts/${encodeURIComponent(artifact.run_id)}/${encodeURIComponent(artifact.artifact_id)}`;
}
</script>

<template>
  <div class="sandbox-panel">
    <div v-if="runtime" class="sandbox-status" :class="runtime.sandbox.available ? 'available' : 'unavailable'">
      <CheckCircle2 v-if="runtime.sandbox.available" :size="19" />
      <TriangleAlert v-else :size="19" />
      <div><strong>Docker Sandbox {{ runtime.sandbox.available ? '可用' : '不可用' }}</strong><p>{{ runtime.sandbox.error || `Server ${runtime.sandbox.docker_version}` }}</p></div>
    </div>

    <div v-if="runtime" class="profile-grid">
      <div><span>Image</span><strong>{{ runtime.sandbox.profile.image }}</strong></div>
      <div><span>Timeout</span><strong>{{ runtime.sandbox.profile.timeout_seconds }}s</strong></div>
      <div><span>Memory</span><strong>{{ runtime.sandbox.profile.memory_mb }}MB</strong></div>
      <div><span>CPU / PIDs</span><strong>{{ runtime.sandbox.profile.cpus }} / {{ runtime.sandbox.profile.pids_limit }}</strong></div>
      <div><span>Network</span><strong>{{ runtime.sandbox.profile.network_disabled ? 'none' : 'enabled' }}</strong></div>
      <div><span>Commands</span><strong>{{ runtime.sandbox.profile.allowed_commands.join(', ') }}</strong></div>
    </div>

    <div v-if="workspaceId" class="workspace-row"><Box :size="16" /><span>Workspace</span><code>{{ workspaceId }}</code></div>

    <div v-if="observations.length" class="sandbox-observations">
      <p class="section-kicker">Sandbox Tool Results</p>
      <details v-for="item in observations" :key="item.step_id">
        <summary><TerminalSquare :size="15" /><strong>{{ item.tool_name }}</strong><span>{{ item.status }}</span></summary>
        <pre>{{ JSON.stringify(item.data, null, 2) }}</pre>
      </details>
    </div>

    <div v-if="artifacts.length" class="artifact-list">
      <p class="section-kicker">Artifacts · {{ artifacts.length }}</p>
      <article v-for="artifact in artifacts" :key="artifact.artifact_id">
        <FileCode2 :size="16" />
        <div><strong>{{ artifact.relative_path }}</strong><span>{{ artifact.mime_type }} · {{ artifact.size_bytes }} bytes</span><code>{{ artifact.sha256.slice(0, 16) }}</code></div>
        <a :href="downloadUrl(artifact)" :download="artifact.relative_path" title="下载 Artifact"><Download :size="16" /></a>
      </article>
    </div>

    <p v-if="!runtime && !observations.length && !artifacts.length" class="muted-text">当前后端没有提供 Sandbox 数据</p>
  </div>
</template>

<style scoped>
.sandbox-panel, .sandbox-observations, .artifact-list { display: grid; gap: 10px; }
.sandbox-status { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 9px; padding: 11px; border: 1px solid #dce5e9; border-radius: 6px; }
.sandbox-status.available { color: #087255; border-color: #bee4d5; background: #eaf7f1; }
.sandbox-status.unavailable { color: #a34337; border-color: #efc8c2; background: #fff0ee; }
.sandbox-status strong { color: #2c4358; font-size: 12px; }
.sandbox-status p { margin: 3px 0 0; color: #68788a; font-size: 10px; overflow-wrap: anywhere; }
.profile-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; }
.profile-grid div { display: grid; gap: 3px; padding: 8px; background: #f4f7f9; border-radius: 5px; min-width: 0; }
.profile-grid span { color: #7a8797; font-size: 9px; text-transform: uppercase; }
.profile-grid strong { color: #30465b; font-size: 10px; overflow-wrap: anywhere; }
.workspace-row { display: grid; grid-template-columns: auto auto minmax(0, 1fr); gap: 7px; align-items: center; color: #52677b; font-size: 10px; }
.workspace-row code { overflow: hidden; text-overflow: ellipsis; }
.sandbox-observations details { border: 1px solid #dce5e9; border-radius: 5px; background: #fff; }
.sandbox-observations summary { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 7px; padding: 9px; cursor: pointer; }
.sandbox-observations summary strong { color: #2c4358; font-size: 11px; }
.sandbox-observations summary span { color: #087255; font-size: 10px; }
.sandbox-observations pre { max-height: 260px; margin: 0; padding: 10px; overflow: auto; color: #d6e7f4; background: #10263b; font-size: 9px; white-space: pre-wrap; overflow-wrap: anywhere; }
.artifact-list article { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 8px; align-items: start; padding: 9px; border: 1px solid #dce5e9; border-radius: 5px; }
.artifact-list article div { display: grid; min-width: 0; gap: 2px; }
.artifact-list strong { color: #2c4358; font-size: 11px; overflow-wrap: anywhere; }
.artifact-list span, .artifact-list code { color: #7a8797; font-size: 9px; }
.artifact-list a { color: #2478a8; }
</style>
