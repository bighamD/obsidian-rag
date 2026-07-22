<script setup lang="ts">
import { BookOpenCheck, X } from "lucide-vue-next";

import type { SkillManifest } from "@/types/production";

defineProps<{
  activeIndex: number;
  candidates: SkillManifest[];
  selectedNames: string[];
}>();

const emit = defineEmits<{
  remove: [name: string];
  select: [name: string];
}>();
</script>

<template>
  <div class="skill-picker-wrap">
    <div v-if="selectedNames.length" class="selected-skill-chips" aria-label="已明确选择的 Skills">
      <span v-for="name in selectedNames" :key="name" class="skill-chip">
        <BookOpenCheck :size="13" />{{ name }}
        <button type="button" :aria-label="`移除 ${name}`" :title="`移除 ${name}`" @click="emit('remove', name)"><X :size="12" /></button>
      </span>
    </div>

    <div v-if="candidates.length" class="skill-picker" role="listbox" aria-label="Skill 候选">
      <button
        v-for="(skill, index) in candidates"
        :key="skill.name"
        type="button"
        role="option"
        :aria-selected="index === activeIndex"
        :class="{ active: index === activeIndex }"
        @mousedown.prevent="emit('select', skill.name)"
      >
        <strong>{{ skill.name }}</strong>
        <span>{{ skill.description }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.skill-picker-wrap { position: relative; display: grid; gap: 7px; }
.selected-skill-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.skill-chip { display: inline-flex; align-items: center; gap: 5px; min-width: 0; padding: 4px 7px; border: 1px solid #b8d9ce; border-radius: 5px; color: #17664f; background: #edf8f4; font-size: 11px; }
.skill-chip button { display: inline-grid; width: 16px; height: 16px; padding: 0; place-items: center; border: 0; color: #50776b; background: transparent; cursor: pointer; }
.skill-picker { position: absolute; z-index: 20; bottom: calc(100% + 8px); left: 0; width: min(460px, 100%); max-height: 240px; overflow-y: auto; padding: 5px; border: 1px solid #cbd8de; border-radius: 7px; background: #fff; box-shadow: 0 14px 32px rgb(31 55 68 / 18%); }
.skill-picker button { display: grid; width: 100%; gap: 3px; padding: 8px 9px; border: 0; border-radius: 5px; text-align: left; background: transparent; cursor: pointer; }
.skill-picker button.active, .skill-picker button:hover { background: #eef5f7; }
.skill-picker strong { color: #27475b; font-size: 12px; }
.skill-picker span { color: #71808d; font-size: 10px; line-height: 1.4; }
</style>
