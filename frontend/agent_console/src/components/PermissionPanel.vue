<script setup lang="ts">
import { Ban, CheckCircle2, ShieldCheck, ShieldQuestion } from "lucide-vue-next";
import { computed } from "vue";

import type { PermissionReport } from "@/types/production";

const props = defineProps<{
  report: PermissionReport | null;
}>();

const principalSummary = computed(() => {
  const principal = props.report?.principal;
  if (!principal) {
    return "-";
  }
  return `${principal.subject_id} · ${principal.roles.join(", ") || "无角色"}`;
});
</script>

<template>
  <div v-if="report" class="permission-panel">
    <div class="permission-summary" :class="{ blocked: !report.all_allowed }">
      <ShieldCheck v-if="report.all_allowed" :size="19" />
      <ShieldQuestion v-else :size="19" />
      <div><strong>{{ report.all_allowed ? '全部允许执行' : '存在受控步骤' }}</strong><p>{{ report.summary }}</p></div>
    </div>

    <div class="detail-list"><span>Principal</span><p>{{ principalSummary }}</p></div>
    <div class="detail-list"><span>Permissions</span><p>{{ report.principal.permissions.join(', ') || '-' }}</p></div>
    <div class="detail-list"><span>Tool allowlist</span><p>{{ report.principal.tool_allowlist.join(', ') || '-' }}</p></div>
    <div class="detail-list"><span>Collection scope</span><p>{{ report.principal.allowed_collections.join(', ') || '-' }}</p></div>
    <div class="permission-counts">
      <span class="allow">allow {{ report.allow_count }}</span>
      <span class="confirm">confirm {{ report.confirm_count }}</span>
      <span class="deny">deny {{ report.deny_count }}</span>
    </div>

    <div class="permission-decisions">
      <article v-for="decision in report.decisions" :key="decision.step_id" :class="['permission-decision', decision.decision]">
        <div class="permission-decision-head">
          <CheckCircle2 v-if="decision.decision === 'allow'" :size="16" />
          <ShieldQuestion v-else-if="decision.decision === 'confirm'" :size="16" />
          <Ban v-else :size="16" />
          <strong>{{ decision.step_id }} · {{ decision.tool_name || decision.kind }}</strong>
          <span>{{ decision.decision }}</span>
        </div>
        <p>{{ decision.reason }}</p>
        <dl>
          <div><dt>risk</dt><dd>{{ decision.risk_level }}</dd></div>
          <div><dt>source</dt><dd>{{ decision.source }}</dd></div>
          <div><dt>required</dt><dd>{{ decision.required_permissions.join(', ') || '-' }}</dd></div>
          <div><dt>collections</dt><dd>{{ decision.collections.join(', ') || '-' }}</dd></div>
        </dl>
        <p v-if="decision.missing_permissions.length" class="permission-error">缺失权限：{{ decision.missing_permissions.join(', ') }}</p>
        <p v-if="decision.denied_collections.length" class="permission-error">禁止知识库：{{ decision.denied_collections.join(', ') }}</p>
        <p v-if="decision.validation_errors.length" class="permission-error">参数错误：{{ decision.validation_errors.join('; ') }}</p>
      </article>
    </div>
  </div>
  <p v-else class="muted-text">当前后端没有返回 Permission Report</p>
</template>
