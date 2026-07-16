<script setup lang="ts">
import { ChevronDown, Send, Settings2, X } from "lucide-vue-next";
import { ref } from "vue";

import type { AgentOptions, SearchMode } from "@/types/production";

const props = defineProps<{
  disabled: boolean;
  isRunning: boolean;
  modelValue: string;
  options: AgentOptions;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string];
  "update:options": [value: AgentOptions];
  submit: [];
}>();

const settingsOpen = ref(false);

function updateOption<Key extends keyof AgentOptions>(key: Key, value: AgentOptions[Key]) {
  emit("update:options", { ...props.options, [key]: value });
}

function submit() {
  if (props.modelValue.trim() && !props.isRunning && !props.disabled) {
    emit("submit");
  }
}

function submitOnEnter(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
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
          <span>Collection</span>
          <input
            :value="options.collection"
            list="collection-options"
            placeholder="留空使用自动路由/默认库"
            :disabled="disabled"
            @input="updateOption('collection', ($event.target as HTMLInputElement).value)"
          />
          <datalist id="collection-options">
            <option value="food_safety" />
            <option value="recipes" />
            <option value="vueuse_core_kb" />
          </datalist>
        </label>
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
      </div>
      <button class="drawer-collapse" type="button" @click="settingsOpen = false"><ChevronDown :size="15" /> 收起参数</button>
    </div>

    <div class="composer">
      <textarea
        :value="modelValue"
        :disabled="isRunning || disabled"
        rows="2"
        aria-label="输入问题"
        placeholder="输入问题"
        @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
        @keydown="submitOnEnter"
      />
      <div class="composer-actions">
        <button class="icon-button" :class="{ active: settingsOpen }" :disabled="disabled" title="运行参数" aria-label="运行参数" @click="settingsOpen = !settingsOpen"><Settings2 :size="18" /></button>
        <button class="send-button" :disabled="!modelValue.trim() || isRunning || disabled" title="发送问题" aria-label="发送问题" @click="submit"><Send :size="18" /></button>
      </div>
    </div>
  </section>
</template>
