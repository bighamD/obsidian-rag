<script setup lang="ts">
import { Braces, FileText, Hash, Layers3 } from "lucide-vue-next";

import type { ContextChunk, SearchHit } from "@/types/production";

type InspectableHit = SearchHit | ContextChunk;

const props = withDefaults(
  defineProps<{
    hits: InspectableHit[];
    emptyText?: string;
  }>(),
  {
    emptyText: "该工具没有返回可展示的检索记录。",
  },
);

function fullText(hit: InspectableHit): string {
  return hit.text?.trim() || hit.text_preview || "未返回知识块正文。";
}

function formatScore(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : value.toFixed(6);
}

function hasContextReason(hit: InspectableHit): hit is ContextChunk {
  return "reason" in hit;
}

function metadataText(hit: InspectableHit): string {
  return JSON.stringify(hit.metadata, null, 2);
}

function metadataNumber(hit: InspectableHit, key: string): number | null {
  const value = hit.metadata[key];
  return typeof value === "number" ? value : null;
}

function rerankRun(hit: InspectableHit): Record<string, unknown> | null {
  const value = hit.metadata.rerank_run;
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}
</script>

<template>
  <p v-if="!props.hits.length" class="retrieval-empty">{{ props.emptyText }}</p>
  <ol v-else class="retrieved-chunk-list" aria-label="检索结果明细">
    <li v-for="(hit, index) in props.hits" :key="`${hit.chunk_id ?? hit.source}-${index}`" class="retrieved-chunk-item">
      <article class="retrieved-chunk-card">
        <header class="retrieved-chunk-head">
          <span class="retrieved-chunk-index">{{ index + 1 }}</span>
          <div class="retrieved-chunk-title">
            <strong><Hash :size="13" />{{ hit.chunk_id || "未标注 chunk_id" }}</strong>
            <span><FileText :size="12" />{{ hit.source }}</span>
          </div>
          <span class="retrieved-chunk-score">score {{ formatScore(hit.score) }}</span>
        </header>

        <dl class="retrieved-chunk-fields">
          <div v-if="hit.topic"><dt>topic</dt><dd>{{ hit.topic }}</dd></div>
          <div v-if="'step_id' in hit && hit.step_id"><dt>step</dt><dd>{{ hit.step_id }}</dd></div>
          <div v-if="hit.dense_rank !== null"><dt>dense rank</dt><dd>{{ hit.dense_rank }}</dd></div>
          <div v-if="hit.keyword_rank !== null"><dt>keyword rank</dt><dd>{{ hit.keyword_rank }}</dd></div>
          <div v-if="hit.dense_score !== null"><dt>dense score</dt><dd>{{ formatScore(hit.dense_score) }}</dd></div>
          <div v-if="hit.keyword_score !== null"><dt>keyword score</dt><dd>{{ formatScore(hit.keyword_score) }}</dd></div>
          <div v-if="hit.hybrid_score !== null"><dt>hybrid score</dt><dd>{{ formatScore(hit.hybrid_score) }}</dd></div>
          <div v-if="metadataNumber(hit, 'retrieval_rank') !== null"><dt>retrieval rank</dt><dd>{{ metadataNumber(hit, "retrieval_rank") }}</dd></div>
          <div v-if="metadataNumber(hit, 'retrieval_score') !== null"><dt>retrieval score</dt><dd>{{ formatScore(metadataNumber(hit, "retrieval_score")) }}</dd></div>
          <div v-if="metadataNumber(hit, 'rerank_rank') !== null"><dt>rerank rank</dt><dd>{{ metadataNumber(hit, "rerank_rank") }}</dd></div>
          <div v-if="metadataNumber(hit, 'rerank_score') !== null"><dt>rerank score</dt><dd>{{ formatScore(metadataNumber(hit, "rerank_score")) }}</dd></div>
          <div v-if="rerankRun(hit)?.model"><dt>rerank model</dt><dd>{{ rerankRun(hit)?.model }}</dd></div>
          <div v-if="rerankRun(hit)?.latency_ms !== undefined"><dt>rerank latency</dt><dd>{{ rerankRun(hit)?.latency_ms }} ms</dd></div>
          <div v-if="rerankRun(hit)?.fallback"><dt>rerank fallback</dt><dd>{{ rerankRun(hit)?.fallback_reason || "true" }}</dd></div>
          <div v-if="hasContextReason(hit) && hit.reason"><dt>选入原因</dt><dd>{{ hit.reason }}</dd></div>
        </dl>

        <section class="retrieved-chunk-content">
          <p><Layers3 :size="13" />完整正文</p>
          <pre>{{ fullText(hit) }}</pre>
        </section>

        <details v-if="Object.keys(hit.metadata).length" class="retrieved-metadata">
          <summary><Braces :size="13" />原始 metadata</summary>
          <pre>{{ metadataText(hit) }}</pre>
        </details>
      </article>
    </li>
  </ol>
</template>
