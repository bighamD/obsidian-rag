<script setup lang="ts">
import {
  Activity,
  BrainCircuit,
  ChevronDown,
  CheckCircle2,
  Clipboard,
  Clock3,
  Database,
  FileSearch,
  Route,
  Search,
  TriangleAlert,
} from "lucide-vue-next";
import { computed, ref } from "vue";

import RetrievedChunkList from "@/components/RetrievedChunkList.vue";
import type { MemorySnapshot, ProductionAskResponse, StepResult } from "@/types/production";
import { formatDateTime, formatDuration, shortId, statusLabel } from "@/utils/format";

const props = defineProps<{
  isRunning: boolean;
  memorySnapshot: MemorySnapshot | null;
  response: ProductionAskResponse | null;
}>();

const activeTab = ref<"overview" | "plan" | "evidence" | "context">("overview");

const agent = computed(() => props.response?.agent_response ?? null);
const run = computed(() => props.response?.run ?? null);
const allStepResults = computed<StepResult[]>(() => {
  if (!agent.value) {
    return [];
  }
  return [...agent.value.step_results, ...agent.value.retry_step_results];
});
const planItems = computed(() =>
  (agent.value?.plan.steps ?? []).map((step) => ({
    step,
    result: allStepResults.value.find((result) => result.step_id === step.id),
  })),
);
const timeline = computed(() => {
  if (!run.value) {
    return [];
  }
  return [
    ...run.value.events.map((event) => ({
      id: `run_${event.name}_${event.occurred_at}`,
      title: event.name,
      detail: event.detail,
      time: event.occurred_at,
      type: "run",
    })),
    ...(agent.value?.trace ?? []).map((trace, index) => ({
      id: `trace_${index}_${trace.node_name}`,
      title: trace.node_name,
      detail: trace.reason || trace.step_type,
      time: "",
      type: "trace",
    })),
  ];
});

async function copy(value: string | null | undefined) {
  if (!value || !navigator.clipboard) {
    return;
  }
  await navigator.clipboard.writeText(value);
}

function toolCalls(toolName: string): StepResult[] {
  return allStepResults.value.filter((result) => result.tool_name === toolName);
}
</script>

<template>
  <aside class="run-inspector" aria-label="运行检查器">
    <div class="inspector-head">
      <div>
        <p class="section-kicker">运行检查器</p>
        <h2>{{ isRunning ? '运行中' : run ? statusLabel(run.status) : '等待运行' }}</h2>
      </div>
      <span class="status-badge" :class="isRunning ? 'running' : run?.status ?? 'idle'">
        <Activity :size="14" /> {{ isRunning ? '运行中' : run ? statusLabel(run.status) : '就绪' }}
      </span>
    </div>

    <div class="inspector-tabs" role="tablist" aria-label="运行详情">
      <button :class="{ active: activeTab === 'overview' }" role="tab" @click="activeTab = 'overview'">概览</button>
      <button :class="{ active: activeTab === 'plan' }" role="tab" @click="activeTab = 'plan'">计划与工具</button>
      <button :class="{ active: activeTab === 'evidence' }" role="tab" @click="activeTab = 'evidence'">证据</button>
      <button :class="{ active: activeTab === 'context' }" role="tab" @click="activeTab = 'context'">上下文</button>
    </div>

    <div v-if="isRunning && !run" class="inspector-empty running">
      <Clock3 :size="22" class="spin" />
      <p>请求已提交</p>
    </div>
    <div v-else-if="!run" class="inspector-empty">
      <Activity :size="22" />
      <p>等待第一条运行记录</p>
    </div>

    <template v-else>
      <section v-if="activeTab === 'overview'" class="inspector-section">
        <div class="run-ids">
          <div class="copy-row"><span>Production Run</span><button title="复制 Production Run ID" @click="copy(run.run_id)"><code>{{ shortId(run.run_id) }}</code><Clipboard :size="14" /></button></div>
          <div class="copy-row"><span>Agent Run</span><button title="复制 Agent Run ID" @click="copy(run.agent_run_id)"><code>{{ shortId(run.agent_run_id) }}</code><Clipboard :size="14" /></button></div>
        </div>

        <div v-if="run.error" class="error-summary">
          <TriangleAlert :size="18" />
          <div><strong>{{ run.error.error_type }}</strong><p>{{ run.error.message }}</p></div>
        </div>

        <div v-if="run.metrics" class="metric-grid">
          <div><span>总耗时</span><strong>{{ formatDuration(run.metrics.timing.duration_ms) }}</strong></div>
          <div><span>图节点</span><strong>{{ run.metrics.graph_node_count }}</strong></div>
          <div><span>Trace 事件</span><strong>{{ run.metrics.trace_event_count }}</strong></div>
          <div><span>检索结果</span><strong>{{ run.metrics.retrieval_result_count }}</strong></div>
          <div><span>Answer token 估算</span><strong>{{ run.metrics.token_estimate.observed_total_tokens }}</strong></div>
          <div><span>开始时间</span><strong>{{ formatDateTime(run.timing.started_at) }}</strong></div>
        </div>

        <div class="timeline-wrap">
          <p class="section-kicker">执行时间线</p>
          <ol class="timeline">
            <li v-for="event in timeline" :key="event.id" :class="event.type">
              <span class="timeline-dot" />
              <div><strong>{{ event.title }}</strong><p>{{ event.detail }}</p></div>
              <time v-if="event.time">{{ formatDateTime(event.time) }}</time>
            </li>
          </ol>
        </div>
      </section>

      <section v-else-if="activeTab === 'plan'" class="inspector-section">
        <div v-if="agent" class="plan-goal"><Route :size="17" /><span>{{ agent.plan.goal }}</span></div>
        <ol v-if="agent" class="plan-list">
          <li v-for="item in planItems" :key="item.step.id">
            <span class="plan-index">{{ item.step.id }}</span>
            <div>
              <div class="plan-title"><strong>{{ item.step.kind }}</strong><span :class="['step-status', item.result?.status ?? 'skipped']">{{ item.result?.status ?? 'planned' }}</span></div>
              <p>{{ item.step.query || item.step.instruction || item.step.reason || '无附加说明' }}</p>
              <details v-if="item.result?.result_count" class="result-disclosure">
                <summary><span><ChevronDown :size="14" />{{ item.result.result_count }} 条结果</span><small>查看检索明细</small></summary>
                <RetrievedChunkList :hits="item.result.results" />
              </details>
              <small v-if="item.result?.error" class="error-text">{{ item.result.error }}</small>
            </div>
          </li>
        </ol>
        <div v-if="run.metrics?.tool_summaries.length" class="tool-summary">
          <p class="section-kicker">工具汇总</p>
          <details v-for="tool in run.metrics.tool_summaries" :key="tool.tool_name" class="tool-disclosure">
            <summary class="tool-row">
              <Search :size="16" /><strong>{{ tool.tool_name }}</strong><span>{{ tool.call_count }} 次调用</span><span>{{ tool.result_count }} 条结果<ChevronDown :size="14" /></span>
            </summary>
            <div class="tool-call-list">
              <article v-for="call in toolCalls(tool.tool_name)" :key="call.step_id" class="tool-call-detail">
                <div><strong>{{ call.step_id }}</strong><span>{{ call.query || call.instruction || call.reason || '无查询参数' }}</span></div>
                <RetrievedChunkList :hits="call.results" :empty-text="call.error || '该次工具调用没有返回检索结果。'" />
              </article>
            </div>
          </details>
        </div>
        <p v-else class="muted-text">本次没有工具调用</p>
      </section>

      <section v-else-if="activeTab === 'evidence'" class="inspector-section">
        <template v-if="agent">
          <div class="evidence-status" :class="agent.evidence_check.is_sufficient ? 'sufficient' : 'insufficient'">
            <CheckCircle2 v-if="agent.evidence_check.is_sufficient" :size="19" />
            <TriangleAlert v-else :size="19" />
            <div><strong>{{ agent.evidence_check.is_sufficient ? '证据充分' : '证据不足' }}</strong><p>{{ agent.evidence_check.reason }}</p></div>
          </div>
          <div class="detail-list"><span>已检查步骤</span><p>{{ agent.evidence_check.checked_step_ids.join(', ') || '-' }}</p></div>
          <div class="detail-list"><span>缺失步骤</span><p>{{ agent.evidence_check.missing_step_ids.join(', ') || '-' }}</p></div>
          <div v-if="agent.evidence_check.missing_points.length" class="list-block"><span>缺失点</span><ul><li v-for="point in agent.evidence_check.missing_points" :key="point">{{ point }}</li></ul></div>
          <div v-if="agent.evidence_check.suggested_queries.length" class="list-block"><span>补搜查询</span><ul><li v-for="query in agent.evidence_check.suggested_queries" :key="query">{{ query }}</li></ul></div>
        </template>
      </section>

      <section v-else class="inspector-section">
        <div class="memory-overview">
          <Database :size="18" />
          <div><strong>Conversation Memory</strong><p>{{ memorySnapshot?.loaded_turn_count ?? 0 }} / {{ memorySnapshot?.total_turn_count ?? 0 }} 条原始 Turn 已载入</p></div>
        </div>
        <div v-if="memorySnapshot?.summary_text" class="summary-text"><span>滚动摘要</span><p>{{ memorySnapshot.summary_text }}</p></div>
        <div v-if="agent" class="context-summary">
          <BrainCircuit :size="18" />
          <div><strong>Answer Context</strong><p>{{ agent.context_bundle.context_summary }}</p><small>预算 {{ agent.context_bundle.token_budget }} · 已选 {{ agent.context_bundle.included_chunks.length }} chunks · 排除 {{ agent.context_bundle.excluded_chunks.length }} chunks</small></div>
        </div>
        <div v-if="agent?.context_bundle.included_chunks.length" class="chunk-list">
          <p class="section-kicker">选入的知识块 · {{ agent.context_bundle.included_chunks.length }}</p>
          <details v-for="chunk in agent.context_bundle.included_chunks" :key="`${chunk.step_id}-${chunk.chunk_id}-${chunk.source}`" class="chunk-disclosure">
            <summary>
              <FileSearch :size="15" />
              <div><strong>{{ chunk.chunk_id || chunk.source }}</strong><span>{{ chunk.source }}</span><p>{{ chunk.text_preview }}</p></div>
              <ChevronDown :size="16" />
            </summary>
            <RetrievedChunkList :hits="[chunk]" />
          </details>
        </div>
      </section>
    </template>
  </aside>
</template>
