<script setup lang="ts">
import { ChevronDown, Send, Settings2, X } from "lucide-vue-next";
import { computed, shallowRef } from "vue";

import SkillPicker from "@/components/SkillPicker.vue";
import type { AgentOptions, SearchMode, SkillManifest } from "@/types/production";

const props = defineProps<{
  disabled: boolean;
  isRunning: boolean;
  mcpAvailable: boolean;
  permissionAvailable: boolean;
  skillAvailable: boolean;
  skills: SkillManifest[];
  sandboxAvailable: boolean;
  modelValue: string;
  options: AgentOptions;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string];
  "update:options": [value: AgentOptions];
  submit: [];
}>();

const settingsOpen = shallowRef(false);
const activeSkillIndex = shallowRef(0);

const slashMatch = computed(() => props.modelValue.match(/(?:^|\s)\/([a-z0-9_-]*)$/i));
const slashQuery = computed(() => slashMatch.value?.[1]?.toLowerCase() ?? "");
const skillCandidates = computed(() => {
  if (!props.skillAvailable || !slashMatch.value) {
    return [];
  }
  return props.skills
    .filter((skill) => !props.options.skillNames.includes(skill.name))
    .filter((skill) => {
      const query = slashQuery.value;
      return !query || skill.name.toLowerCase().includes(query) || skill.description.toLowerCase().includes(query);
    })
    .slice(0, 8);
});

function updateOption<Key extends keyof AgentOptions>(key: Key, value: AgentOptions[Key]) {
  emit("update:options", { ...props.options, [key]: value });
}

function submit() {
  if (props.modelValue.trim() && !props.isRunning && !props.disabled) {
    emit("submit");
  }
}

function submitOnEnter(event: KeyboardEvent) {
  if (skillCandidates.value.length) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const direction = event.key === "ArrowDown" ? 1 : -1;
      activeSkillIndex.value = (
        activeSkillIndex.value + direction + skillCandidates.value.length
      ) % skillCandidates.value.length;
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      selectSkill(skillCandidates.value[activeSkillIndex.value]?.name);
      return;
    }
  }
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}

function updateQuestion(value: string) {
  activeSkillIndex.value = 0;
  emit("update:modelValue", value);
}

function selectSkill(name: string | undefined) {
  if (!name) {
    return;
  }
  updateOption("skillNames", [...new Set([...props.options.skillNames, name])]);
  const match = slashMatch.value;
  if (match && match.index !== undefined) {
    const prefix = props.modelValue.slice(0, match.index).trimEnd();
    updateQuestion(prefix ? `${prefix} ` : "");
  }
}

function removeSkill(name: string) {
  updateOption("skillNames", props.options.skillNames.filter((item) => item !== name));
}

function selectSkillFromSettings(value: string) {
  selectSkill(value || undefined);
}
</script>

<template>
  <section class="composer-wrap" aria-label="提问输入区">
    <div v-if="settingsOpen" class="settings-drawer">
      <div class="settings-head">
        <strong>运行参数</strong>
        <button class="icon-button small" title="关闭参数" aria-label="关闭参数" @click="settingsOpen = false"><X :size="16" /></button>
      </div>
      <div class="settings-grid">
        <label>
          <span>检索模式</span>
          <span class="segmented-control">
            <button
              v-for="mode in (['hybrid', 'dense', 'keyword'] as SearchMode[])"
              :key="mode"
              type="button"
              :disabled="disabled"
              :class="{ selected: options.mode === mode }"
              @click="updateOption('mode', mode)"
            >{{ mode }}</button>
          </span>
        </label>
        <label><span>Top K</span><input :value="options.topK" :disabled="disabled" type="number" min="1" max="20" @input="updateOption('topK', Number(($event.target as HTMLInputElement).value))" /></label>
        <label><span>最大步骤</span><input :value="options.maxSteps" :disabled="disabled" type="number" min="1" max="8" @input="updateOption('maxSteps', Number(($event.target as HTMLInputElement).value))" /></label>
        <label><span>补搜次数</span><input :value="options.maxRetries" :disabled="disabled" type="number" min="0" max="3" @input="updateOption('maxRetries', Number(($event.target as HTMLInputElement).value))" /></label>
        <label><span>Memory Window</span><input :value="options.memoryWindow" :disabled="disabled" type="number" min="0" max="20" @input="updateOption('memoryWindow', Number(($event.target as HTMLInputElement).value))" /></label>
        <label><span>Context Chunks</span><input :value="options.contextMaxChunks" :disabled="disabled" type="number" min="1" max="20" @input="updateOption('contextMaxChunks', Number(($event.target as HTMLInputElement).value))" /></label>
        <label><span>Context Budget</span><input :value="options.contextTokenBudget" :disabled="disabled" type="number" min="500" max="20000" step="500" @input="updateOption('contextTokenBudget', Number(($event.target as HTMLInputElement).value))" /></label>
        <label class="toggle-setting"><span>Memory Compaction</span><input :checked="options.memoryCompactionEnabled" :disabled="disabled" type="checkbox" @change="updateOption('memoryCompactionEnabled', ($event.target as HTMLInputElement).checked)" /></label>
        <label v-if="mcpAvailable" class="toggle-setting"><span>MCP Tools</span><input :checked="options.mcpEnabled" :disabled="disabled" type="checkbox" @change="updateOption('mcpEnabled', ($event.target as HTMLInputElement).checked)" /></label>
        <label v-if="permissionAvailable">
          <span>权限预设</span>
          <select :value="options.permissionProfile" :disabled="disabled" @change="updateOption('permissionProfile', ($event.target as HTMLSelectElement).value as AgentOptions['permissionProfile'])">
            <option value="standard">标准只读</option>
            <option value="knowledge_only">仅知识库</option>
            <option value="restricted">受限主体</option>
            <option v-if="sandboxAvailable" value="sandbox">Sandbox 执行</option>
          </select>
        </label>
        <label v-if="skillAvailable">
          <span>添加显式 Skill</span>
          <select :disabled="disabled" value="" @change="selectSkillFromSettings(($event.target as HTMLSelectElement).value); ($event.target as HTMLSelectElement).value = ''">
            <option value="">选择 Skill</option>
            <option v-for="skill in skills" :key="skill.name" :value="skill.name" :disabled="options.skillNames.includes(skill.name)">{{ skill.name }}</option>
          </select>
        </label>
        <label v-if="skillAvailable">
          <span>Skill 选择模式</span>
          <select :value="options.skillSelectionMode" :disabled="disabled" @change="updateOption('skillSelectionMode', ($event.target as HTMLSelectElement).value as AgentOptions['skillSelectionMode'])">
            <option value="augment">显式 + 隐式补充</option>
            <option value="exclusive">仅显式 Skills</option>
          </select>
        </label>
        <label v-if="skillAvailable" class="toggle-setting"><span>Skill Router</span><input :checked="options.skillRouterEnabled" :disabled="disabled" type="checkbox" @change="updateOption('skillRouterEnabled', ($event.target as HTMLInputElement).checked)" /></label>
        <label v-if="sandboxAvailable" class="toggle-setting"><span>Sandbox Tools</span><input :checked="options.sandboxEnabled" :disabled="disabled" type="checkbox" @change="updateOption('sandboxEnabled', ($event.target as HTMLInputElement).checked)" /></label>
      </div>
      <button class="drawer-collapse" type="button" @click="settingsOpen = false"><ChevronDown :size="15" /> 收起参数</button>
    </div>

    <SkillPicker
      v-if="skillAvailable"
      :active-index="activeSkillIndex"
      :candidates="skillCandidates"
      :selected-names="options.skillNames"
      @remove="removeSkill"
      @select="selectSkill"
    />
    <div class="composer">
      <textarea
        :value="modelValue"
        :disabled="isRunning || disabled"
        rows="2"
        aria-label="输入问题"
        placeholder="输入问题"
        @input="updateQuestion(($event.target as HTMLTextAreaElement).value)"
        @keydown="submitOnEnter"
      />
      <div class="composer-actions">
        <button class="icon-button" :class="{ active: settingsOpen }" :disabled="disabled" title="运行参数" aria-label="运行参数" @click="settingsOpen = !settingsOpen"><Settings2 :size="18" /></button>
        <button class="send-button" :disabled="!modelValue.trim() || isRunning || disabled" title="发送问题" aria-label="发送问题" @click="submit"><Send :size="18" /></button>
      </div>
    </div>
  </section>
</template>
