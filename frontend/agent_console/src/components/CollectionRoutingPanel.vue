<script setup lang="ts">
import { AlertTriangle, BookOpen, CheckCircle2, Database, Route } from "lucide-vue-next";
import { computed } from "vue";

import type { CollectionRuntimeResponse, RetrievalScope, StepResult } from "@/types/production";

const props = defineProps<{
  runtime: CollectionRuntimeResponse | null;
  scope: RetrievalScope | null;
  stepResults: StepResult[];
}>();

const searchSteps = computed(() => props.stepResults.filter((item) => item.kind === "search"));
const selected = computed(() => new Set([
  ...(props.scope?.selected_ids ?? []),
  ...(props.scope?.selected_collections ?? []),
]));
function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}
function requestedCollections(step: StepResult): string[] {
  return stringList(step.arguments.collections);
}
function executedCollections(step: StepResult): string[] {
  const direct = stringList(step.metadata.selected_collections);
  if (direct.length) return direct;
  const scope = step.metadata.retrieval_scope as RetrievalScope | undefined;
  return scope?.selected_collections ?? [];
}
const statusTone = computed(() => {
  if (!props.scope) return "idle";
  return ["selected", "multi_selected", "explicit", "disabled"].includes(props.scope.status)
    ? "success"
    : props.scope.status === "not_required" ? "idle" : "warning";
});
</script>

<template>
  <div class="collection-routing-panel">
    <div v-if="scope" class="routing-summary" :class="statusTone">
      <Route :size="18" />
      <div><strong>{{ scope.status }}</strong><p>{{ scope.reason }}</p><small v-if="scope.confidence !== null">confidence {{ scope.confidence.toFixed(2) }}</small></div>
      <CheckCircle2 v-if="statusTone === 'success'" :size="17" />
      <AlertTriangle v-else-if="statusTone === 'warning'" :size="17" />
    </div>

    <div v-if="scope?.selected_collections.length" class="selected-scope">
      <p class="section-kicker">Run Collection Summary</p>
      <div class="collection-chips"><span v-for="collection in scope.selected_collections" :key="collection">{{ collection }}</span></div>
    </div>

    <div v-if="searchSteps.length" class="search-scope-list">
      <p class="section-kicker">Planner Search Steps</p>
      <article v-for="step in searchSteps" :key="step.step_id" class="search-scope-row">
        <div class="search-scope-head"><strong>{{ step.step_id }}</strong><span>{{ step.status }}</span></div>
        <p>{{ step.query }}</p>
        <small>Planner：{{ requestedCollections(step).join(', ') || 'default' }}</small>
        <small>执行：{{ executedCollections(step).join(', ') || 'none' }}</small>
        <small v-if="step.error" class="scope-error">{{ step.error }}</small>
      </article>
    </div>

    <div v-if="runtime?.knowledge_bases.length" class="knowledge-base-list">
      <p class="section-kicker">Knowledge Base Catalog</p>
      <article v-for="item in runtime.knowledge_bases" :key="item.id" :class="['knowledge-base-row', { selected: selected.has(item.id) || selected.has(item.collection) }]">
        <BookOpen :size="16" />
        <div><strong>{{ item.id }}</strong><span>{{ item.collection }}</span><p>{{ item.description }}</p><small>{{ item.triggers.join(' · ') }}</small></div>
        <span class="candidate-state">{{ selected.has(item.id) || selected.has(item.collection) ? 'used' : item.enabled ? 'available' : 'disabled' }}</span>
      </article>
    </div>

    <div v-if="scope && Object.keys(scope.errors).length" class="routing-errors">
      <p class="section-kicker">Collection Errors</p>
      <p v-for="(message, key) in scope.errors" :key="key"><AlertTriangle :size="13" /><strong>{{ key }}</strong>{{ message }}</p>
    </div>

    <div v-if="runtime" class="registry-path"><Database :size="14" /><code>{{ runtime.registry_path }}</code></div>
    <p v-if="!runtime && !scope" class="muted-text">当前后端没有提供 Collection Selection 数据</p>
  </div>
</template>

<style scoped>
.collection-routing-panel { display: grid; gap: 14px; }
.routing-summary { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 9px; align-items: start; padding: 11px; border: 1px solid #dce5e9; border-radius: 6px; background: #f7f9fa; }
.routing-summary.success { color: #087255; border-color: #bee4d5; background: #eaf7f1; }
.routing-summary.warning { color: #995b14; border-color: #efd2aa; background: #fff5e8; }
.routing-summary strong, .knowledge-base-row strong { color: #2c4358; font-size: 12px; }
.routing-summary p, .knowledge-base-row p { margin: 3px 0 0; color: #68788a; font-size: 11px; line-height: 1.45; }
.routing-summary small, .knowledge-base-row span, .knowledge-base-row small { color: #7a8797; font-size: 10px; }
.selected-scope, .knowledge-base-list, .routing-errors, .search-scope-list { display: grid; gap: 7px; }
.collection-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.collection-chips span { padding: 4px 7px; color: #205d51; background: #dff3eb; border-radius: 4px; font-size: 10px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.knowledge-base-row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 8px; align-items: start; padding: 9px; border: 1px solid #dce5e9; border-radius: 5px; background: #fff; }
.knowledge-base-row.selected { border-color: #78cbb2; box-shadow: inset 3px 0 #25a87d; }
.knowledge-base-row div { display: grid; min-width: 0; gap: 2px; }
.candidate-state { padding: 2px 5px; border-radius: 3px; background: #edf1f4; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; white-space: nowrap; }
.knowledge-base-row.selected .candidate-state { color: #087255; background: #def3e9; }
.search-scope-row { display: grid; gap: 4px; padding: 9px; border: 1px solid #dce5e9; border-radius: 5px; background: #fff; }
.search-scope-head { display: flex; justify-content: space-between; gap: 8px; }
.search-scope-head strong { color: #2c4358; font-size: 11px; }
.search-scope-head span { color: #087255; font-size: 10px; }
.search-scope-row p { margin: 0; color: #526678; font-size: 11px; }
.search-scope-row small { color: #7a8797; font-size: 10px; }
.search-scope-row .scope-error { color: #a34337; }
.routing-errors p { display: grid; grid-template-columns: auto auto minmax(0, 1fr); gap: 5px; align-items: start; margin: 0; padding: 7px; color: #a34337; background: #fff0ee; border-radius: 4px; font-size: 10px; overflow-wrap: anywhere; }
.registry-path { display: flex; gap: 6px; min-width: 0; align-items: center; color: #7a8797; }
.registry-path code { overflow: hidden; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
</style>
