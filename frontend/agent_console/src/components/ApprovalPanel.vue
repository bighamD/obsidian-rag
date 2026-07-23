<script setup lang="ts">
import { Check, FilePenLine, ShieldAlert, X } from "lucide-vue-next";
import { reactive, watch } from "vue";

import type { ApprovalAction, ApprovalRecord } from "@/types/production";

const props = defineProps<{
  approval: ApprovalRecord;
  busy: boolean;
}>();

const emit = defineEmits<{
  decide: [action: ApprovalAction, stepArguments: Record<string, Record<string, unknown>>];
}>();

const drafts = reactive<Record<string, string>>({});
const errors = reactive<Record<string, string>>({});

watch(
  () => props.approval,
  (approval) => {
    for (const key of Object.keys(drafts)) {
      delete drafts[key];
      delete errors[key];
    }
    for (const step of approval.request.steps) {
      drafts[step.step_id] = JSON.stringify(step.arguments, null, 2);
    }
  },
  { immediate: true },
);

function decide(action: ApprovalAction) {
  if (action !== "edit") {
    emit("decide", action, {});
    return;
  }
  const stepArguments: Record<string, Record<string, unknown>> = {};
  let valid = true;
  for (const step of props.approval.request.steps) {
    try {
      const value = JSON.parse(drafts[step.step_id] ?? "{}") as unknown;
      if (!value || typeof value !== "object" || Array.isArray(value)) {
        throw new Error("必须是 JSON object");
      }
      stepArguments[step.step_id] = value as Record<string, unknown>;
      errors[step.step_id] = "";
    } catch (error) {
      valid = false;
      errors[step.step_id] = error instanceof Error ? error.message : "JSON 格式错误";
    }
  }
  if (valid) {
    emit("decide", "edit", stepArguments);
  }
}
</script>

<template>
  <section class="approval-panel" :class="approval.status">
    <div class="approval-heading">
      <span class="approval-icon"><ShieldAlert :size="18" /></span>
      <div>
        <strong>{{ approval.status === 'pending' ? '需要人工审批' : '审批已完成' }}</strong>
        <p>{{ approval.request.summary }}</p>
      </div>
      <span class="approval-status">{{ approval.status === 'pending' ? 'WAITING' : approval.decision?.action.toUpperCase() }}</span>
    </div>

    <div class="approval-steps">
      <details v-for="step in approval.request.steps" :key="step.step_id" :open="approval.status === 'pending'">
        <summary><strong>{{ step.tool_name }}</strong><span>{{ step.step_id }} · {{ step.risk_level }}</span></summary>
        <p>{{ step.reason }}</p>
        <textarea
          v-if="approval.status === 'pending'"
          v-model="drafts[step.step_id]"
          :aria-label="`${step.tool_name} 参数`"
          spellcheck="false"
        />
        <pre v-else>{{ JSON.stringify(approval.decision?.step_arguments[step.step_id] ?? step.arguments, null, 2) }}</pre>
        <span v-if="errors[step.step_id]" class="approval-error">{{ errors[step.step_id] }}</span>
      </details>
    </div>

    <div v-if="approval.status === 'pending'" class="approval-actions">
      <button class="deny" :disabled="busy" @click="decide('deny')"><X :size="16" />拒绝</button>
      <button class="edit" :disabled="busy" @click="decide('edit')"><FilePenLine :size="16" />修改后允许</button>
      <button class="allow" :disabled="busy" @click="decide('allow')"><Check :size="16" />允许执行</button>
    </div>
    <p v-else class="approval-result">
      决定：{{ approval.decision?.action }}<span v-if="approval.decision?.comment"> · {{ approval.decision.comment }}</span>
    </p>
  </section>
</template>

<style scoped>
.approval-panel {
  position: relative;
  z-index: 3;
  flex: 0 0 auto;
  max-height: min(42vh, 420px);
  margin: 0 20px 12px;
  padding: 14px;
  overflow-y: auto;
  border: 1px solid #e6b84b;
  border-radius: 8px;
  background: #fffaf0;
  color: #263247;
  pointer-events: auto;
}

.approval-panel.resolved {
  border-color: #79b895;
  background: #f2fbf5;
}

.approval-heading,
.approval-actions,
.approval-heading > div,
.approval-steps summary {
  display: flex;
  align-items: center;
}

.approval-heading {
  gap: 10px;
}

.approval-heading > div {
  min-width: 0;
  flex: 1;
  align-items: flex-start;
  flex-direction: column;
  gap: 2px;
}

.approval-heading p,
.approval-steps p,
.approval-result {
  margin: 0;
  color: #68748a;
  font-size: 12px;
  line-height: 1.55;
}

.approval-icon {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: 7px;
  background: #f5d77e;
  color: #634800;
}

.approval-status {
  color: #7b5b08;
  font-size: 10px;
  font-weight: 700;
}

.approval-steps {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.approval-steps details {
  padding: 9px 10px;
  border: 1px solid #e8ddc2;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.72);
}

.approval-steps summary {
  cursor: pointer;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
}

.approval-steps summary span {
  color: #8892a4;
  font-size: 10px;
}

.approval-steps p {
  margin-top: 7px;
}

.approval-steps textarea,
.approval-steps pre {
  box-sizing: border-box;
  width: 100%;
  min-height: 82px;
  max-height: 180px;
  margin: 8px 0 0;
  padding: 9px;
  overflow: auto;
  border: 1px solid #d8dce5;
  border-radius: 5px;
  background: #172033;
  color: #dbe8ff;
  font: 11px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace;
  resize: vertical;
  white-space: pre-wrap;
}

.approval-actions {
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.approval-actions button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}

.approval-actions button:disabled {
  cursor: wait;
  opacity: 0.55;
}

.approval-actions .deny {
  border-color: #e3a7a7;
  background: #fff;
  color: #a23b3b;
}

.approval-actions .edit {
  border-color: #b6bfd2;
  background: #fff;
  color: #45526a;
}

.approval-actions .allow {
  background: #257250;
  color: #fff;
}

.approval-error {
  color: #b33434;
  font-size: 11px;
}

.approval-result {
  margin-top: 10px;
  font-weight: 600;
}

@media (max-width: 650px) {
  .approval-panel {
    max-height: min(48vh, 420px);
    margin: 0 12px 10px;
    padding: 12px;
  }

  .approval-heading {
    align-items: flex-start;
  }

  .approval-actions {
    flex-wrap: wrap;
  }
}
</style>
