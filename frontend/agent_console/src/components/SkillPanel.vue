<script setup lang="ts">
import { BookOpenCheck, BrainCircuit, CircleSlash2, FolderSearch } from "lucide-vue-next";
import { computed } from "vue";

import type { SkillLoadedSummary, SkillRuntimeResponse, SkillSelection } from "@/types/production";

const props = defineProps<{
  runtime: SkillRuntimeResponse | null;
  selection: SkillSelection | null;
  loadedSkill: SkillLoadedSummary | null;
  loadedSkills: SkillLoadedSummary[];
}>();

const selected = computed(() => new Set(
  props.selection?.selected_skills?.length
    ? props.selection.selected_skills
    : props.selection?.selected_skill ? [props.selection.selected_skill] : [],
));
const effectiveLoadedSkills = computed(() => (
  props.loadedSkills.length ? props.loadedSkills : props.loadedSkill ? [props.loadedSkill] : []
));
</script>

<template>
  <div class="skill-panel">
    <div v-if="selection" class="skill-selection" :class="selection.selected_skill ? 'selected' : 'skipped'">
      <BrainCircuit v-if="selection.selected_skill" :size="19" />
      <CircleSlash2 v-else :size="19" />
      <div><strong>{{ selection.status }}</strong><p>{{ selection.reason }}</p><small v-if="selection.confidence !== null">confidence {{ selection.confidence.toFixed(2) }}</small></div>
    </div>

    <div v-if="selection?.routing_decision" class="routing-decision">
      <strong>{{ selection.routing_decision.path }}</strong>
      <p>{{ selection.routing_decision.reason }}</p>
      <small>Router LLM：{{ selection.router_called ? '已调用' : '已跳过' }}<template v-if="selection.routing_decision.top_score !== null"> · top {{ selection.routing_decision.top_score.toFixed(2) }}</template><template v-if="selection.routing_decision.score_margin !== null"> · margin {{ selection.routing_decision.score_margin.toFixed(2) }}</template></small>
    </div>

    <div v-if="effectiveLoadedSkills.length" class="loaded-skill-list">
      <div v-for="skill in effectiveLoadedSkills" :key="skill.name" class="loaded-skill">
        <BookOpenCheck :size="18" />
        <div><strong>{{ skill.name }}</strong><p>{{ skill.description }}</p><small>{{ skill.path }} · 约 {{ skill.estimated_tokens }} tokens · {{ selection?.explicit_skills?.includes(skill.name) ? 'explicit' : 'implicit' }}</small></div>
      </div>
    </div>

    <div v-if="selection?.candidates?.length" class="skill-score-list">
      <p class="section-kicker">Matcher Scores</p>
      <div v-for="candidate in selection?.candidates ?? []" :key="candidate.name" class="skill-score-row">
        <strong>{{ candidate.name }}</strong><span>{{ candidate.score.toFixed(2) }}</span>
        <small>BM25 {{ candidate.bm25_score.toFixed(2) }} · overlap {{ candidate.overlap_score.toFixed(2) }} · trigger {{ candidate.trigger_score.toFixed(2) }}</small>
      </div>
    </div>

    <div v-if="runtime?.skills.length" class="skill-candidates">
      <p class="section-kicker">Router Candidates</p>
      <article v-for="skill in runtime.skills" :key="skill.name" :class="{ selected: selected.has(skill.name) }">
        <FolderSearch :size="16" />
        <div><strong>{{ skill.name }}</strong><p>{{ skill.description }}</p><small>{{ skill.triggers.join(' · ') || '无 triggers' }}</small></div>
        <span>{{ selected.has(skill.name) ? 'selected' : 'candidate' }}</span>
      </article>
    </div>

    <div v-if="runtime?.errors.length" class="skill-errors"><p v-for="error in runtime.errors" :key="error">{{ error }}</p></div>
    <p v-if="runtime" class="skill-root"><code>{{ runtime.root }}</code></p>
    <p v-if="!runtime && !selection" class="muted-text">当前后端没有提供 Skill Router 数据</p>
  </div>
</template>

<style scoped>
.skill-panel, .skill-candidates, .loaded-skill-list, .skill-score-list { display: grid; gap: 10px; }
.skill-selection, .loaded-skill { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 9px; align-items: start; padding: 11px; border: 1px solid #dce5e9; border-radius: 6px; background: #f7f9fa; }
.skill-selection.selected { color: #087255; border-color: #bee4d5; background: #eaf7f1; }
.skill-selection.skipped { color: #6e5a28; border-color: #ead9ad; background: #fff9e9; }
.skill-selection strong, .loaded-skill strong, .skill-candidates strong { color: #2c4358; font-size: 12px; }
.skill-selection p, .loaded-skill p, .skill-candidates p { margin: 3px 0 0; color: #68788a; font-size: 11px; line-height: 1.45; }
.skill-selection small, .loaded-skill small, .skill-candidates small { color: #7a8797; font-size: 10px; }
.loaded-skill { color: #315f8a; border-color: #c8dced; background: #eef6fb; }
.routing-decision { padding: 10px; border: 1px solid #d9d0ed; border-radius: 6px; background: #f6f2fb; }
.routing-decision strong { color: #5f4780; font-size: 12px; }
.routing-decision p { margin: 3px 0; color: #6d6480; font-size: 11px; line-height: 1.45; }
.routing-decision small { color: #81758e; font-size: 10px; }
.skill-score-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 3px 8px; padding: 8px; border: 1px solid #dce5e9; border-radius: 5px; background: #fff; }
.skill-score-row strong { color: #2c4358; font-size: 11px; }
.skill-score-row span { color: #087255; font: 600 11px ui-monospace, SFMono-Regular, Menlo, monospace; }
.skill-score-row small { grid-column: 1 / -1; color: #7a8797; font-size: 9px; }
.skill-candidates article { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 8px; align-items: start; padding: 9px; border: 1px solid #dce5e9; border-radius: 5px; background: #fff; }
.skill-candidates article.selected { border-color: #78cbb2; box-shadow: inset 3px 0 #25a87d; }
.skill-candidates article > div { display: grid; min-width: 0; gap: 2px; }
.skill-candidates article > span { padding: 2px 5px; border-radius: 3px; color: #718092; background: #edf1f4; font-size: 10px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.skill-errors p { margin: 0; padding: 7px; color: #a34337; background: #fff0ee; border-radius: 4px; font-size: 10px; overflow-wrap: anywhere; }
.skill-root { margin: 0; color: #7a8797; font-size: 9px; overflow-wrap: anywhere; }
</style>
