<script setup lang="ts">
import { Download, FileText } from "lucide-vue-next";

import type { ArtifactRecord } from "@/types/production";

defineProps<{
  artifacts: ArtifactRecord[];
}>();

const apiBase = import.meta.env.VITE_API_BASE ?? "/api";

function downloadUrl(artifact: ArtifactRecord): string {
  return `${apiBase}/sandbox/artifacts/${encodeURIComponent(artifact.run_id)}/${encodeURIComponent(artifact.artifact_id)}`;
}

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`;
  }
  return `${(sizeBytes / 1024).toFixed(1)} KB`;
}
</script>

<template>
  <div v-if="artifacts.length" class="artifact-downloads" aria-label="生成的文件">
    <span class="artifact-heading">生成的文件</span>
    <a
      v-for="artifact in artifacts"
      :key="artifact.artifact_id"
      class="artifact-link"
      :href="downloadUrl(artifact)"
      :download="artifact.relative_path"
      :title="`下载 ${artifact.relative_path}`"
    >
      <FileText :size="15" />
      <span class="artifact-name">{{ artifact.relative_path }}</span>
      <span class="artifact-size">{{ formatFileSize(artifact.size_bytes) }}</span>
      <Download :size="15" />
    </a>
  </div>
</template>

<style scoped>
.artifact-downloads {
  display: grid;
  gap: 6px;
  margin-top: 12px;
}

.artifact-heading {
  color: #6f7d8e;
  font-size: 10px;
  font-weight: 650;
}

.artifact-link {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  gap: 8px;
  align-items: center;
  width: min(100%, 520px);
  padding: 9px 10px;
  color: #245b7a;
  text-decoration: none;
  background: #f5f9fb;
  border: 1px solid #d8e5eb;
  border-radius: 6px;
}

.artifact-link:hover {
  color: #174d6d;
  background: #edf6fa;
  border-color: #b9d5e2;
}

.artifact-name {
  min-width: 0;
  overflow: hidden;
  font-size: 12px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-size {
  color: #7b8998;
  font-size: 10px;
}
</style>
