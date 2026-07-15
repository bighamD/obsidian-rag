import { computed, onMounted, reactive, ref, watch } from "vue";

import {
  fetchConversation,
  fetchHealth,
  fetchRuns,
  normalizeProductionResponse,
  streamAgent,
} from "@/api/production-client";
import type {
  AgentStreamEvent,
  AgentAskPayload,
  AgentOptions,
  AgentProgress,
  ConsoleMessage,
  ConsoleSession,
  MemorySnapshot,
  ProductionAskResponse,
  RunRecord,
} from "@/types/production";

const STORAGE_KEY = "obsidian-rag.v3.10.1.console-sessions";
const MAX_SESSIONS = 12;
const MAX_MESSAGES_PER_SESSION = 40;

const defaultOptions: AgentOptions = {
  collection: "food_safety",
  memoryWindow: 3,
  memoryCompactionEnabled: true,
  memoryCompactionTriggerTurns: 4,
  memoryCompactionTriggerTokens: 3000,
  topK: 5,
  mode: "hybrid",
  maxSteps: 4,
  maxRetries: 1,
  contextMaxChunks: 4,
  contextTokenBudget: 4000,
};

export function useAgentConsole() {
  const sessions = ref<ConsoleSession[]>(loadSessions());
  const activeConversationId = ref(sessions.value[0]?.id ?? createConversationId());
  const response = ref<ProductionAskResponse | null>(null);
  const recentRuns = ref<RunRecord[]>([]);
  const memorySnapshot = ref<MemorySnapshot | null>(null);
  const isRunning = ref(false);
  const apiOnline = ref<boolean | null>(null);
  const requestError = ref("");
  const options = reactive<AgentOptions>({ ...defaultOptions });

  if (sessions.value.length === 0) {
    sessions.value = [newSession(activeConversationId.value)];
  }

  const activeSession = computed(
    () => sessions.value.find((session) => session.id === activeConversationId.value) ?? sessions.value[0],
  );

  watch(
    sessions,
    (value) => saveSessions(value),
    { deep: true },
  );

  onMounted(async () => {
    await refreshWorkspace();
  });

  async function refreshWorkspace() {
    await Promise.all([refreshHealth(), refreshRuns(), hydrateConversation(activeConversationId.value)]);
  }

  async function refreshHealth() {
    try {
      const health = await fetchHealth();
      apiOnline.value = health.status === "ok";
    } catch {
      apiOnline.value = false;
    }
  }

  async function refreshRuns() {
    try {
      recentRuns.value = await fetchRuns();
    } catch {
      recentRuns.value = [];
    }
  }

  async function hydrateConversation(conversationId: string) {
    const session = getSessionFrom(sessions.value, conversationId);
    response.value = latestSessionRun(session);
    try {
      const conversation = await fetchConversation(conversationId, options.memoryWindow);
      memorySnapshot.value = conversation.memory_snapshot;
      if (session && session.messages.length === 0) {
        session.messages = conversation.memory_snapshot.recent_turns.flatMap((turn) => [
          createMessage("user", turn.user_message, turn.created_at),
          createMessage("assistant", turn.assistant_message, turn.created_at, turn.sources),
        ]);
      }
    } catch {
      memorySnapshot.value = null;
    }
  }

  async function selectConversation(conversationId: string) {
    activeConversationId.value = conversationId;
    requestError.value = "";
    await hydrateConversation(conversationId);
  }

  function createConversation() {
    const session = newSession(createConversationId());
    sessions.value = [session, ...sessions.value].slice(0, MAX_SESSIONS);
    activeConversationId.value = session.id;
    response.value = null;
    memorySnapshot.value = null;
    requestError.value = "";
  }

  async function submit(question: string) {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isRunning.value) {
      return;
    }
    const session = getSessionFrom(sessions.value, activeConversationId.value);
    if (!session) {
      return;
    }

    appendMessage(session, createMessage("user", trimmedQuestion));
    const assistantDraft = createStreamingAssistantDraft();
    appendMessage(session, assistantDraft);
    session.title = compactTitle(trimmedQuestion);
    session.updatedAt = new Date().toISOString();
    isRunning.value = true;
    response.value = null;
    requestError.value = "";

    try {
      const result = await streamAgent(
        buildAgentAskPayload(trimmedQuestion, activeConversationId.value, options),
        (event) => applyStreamEvent(event, assistantDraft),
      );
      response.value = result;
      const assistant = result.agent_response;
      if (assistant) {
        reconcileAssistantMessage(assistantDraft, result);
        memorySnapshot.value = assistant.memory_snapshot;
      } else {
        assistantDraft.role = "error";
        assistantDraft.text = result.run.error?.message ?? "本次运行没有生成可展示的答案。";
        assistantDraft.run = result;
        assistantDraft.isStreaming = false;
      }
      await refreshRuns();
    } catch (error) {
      const message = error instanceof Error ? error.message : "请求失败。";
      requestError.value = message;
      markStreamError(assistantDraft, message);
    } finally {
      isRunning.value = false;
      session.updatedAt = new Date().toISOString();
    }
  }

  function applyStreamEvent(event: AgentStreamEvent, assistantDraft: ConsoleMessage) {
    if (event.name === "progress") {
      applyProgressEvent(assistantDraft, event);
    }
    if (event.name === "answer_delta") {
      applyAnswerDelta(assistantDraft, event);
    }
    if (event.data.run) {
      response.value = {
        run: event.data.run,
        agent_response: response.value?.agent_response ?? null,
        skill_result: response.value?.skill_result ?? null,
      };
    }
    if (event.data.response) {
      response.value = normalizeProductionResponse(event.data.response);
    }
  }

  return {
    activeConversationId,
    activeSession,
    apiOnline,
    createConversation,
    hydrateConversation,
    isRunning,
    memorySnapshot,
    options,
    recentRuns,
    refreshWorkspace,
    requestError,
    response,
    selectConversation,
    sessions,
    submit,
  };
}

export function applyAnswerDelta(message: ConsoleMessage, event: AgentStreamEvent): boolean {
  const { message_id: messageId, sequence, delta } = event.data;
  if (!messageId || typeof sequence !== "number" || !delta) {
    return false;
  }
  if (message.streamMessageId && message.streamMessageId !== messageId) {
    return false;
  }
  if (sequence <= (message.streamSequence ?? 0)) {
    return false;
  }
  message.streamMessageId = messageId;
  message.streamSequence = sequence;
  message.currentProgress = "正在生成回答…";
  message.text += delta;
  return true;
}

export function createStreamingAssistantDraft(): ConsoleMessage {
  const message = reactive(createMessage("assistant", ""));
  message.isStreaming = true;
  message.streamSequence = 0;
  message.currentProgress = "正在生成回答…";
  return message;
}

export function applyProgressEvent(message: ConsoleMessage, event: AgentStreamEvent): boolean {
  const payload = event.data.agent;
  if (!payload?.phase || !payload.status) {
    return false;
  }
  const progress: AgentProgress = {
    phase: payload.phase,
    status: payload.status,
    collection: payload.collection,
    result_count: payload.result_count,
  };
  message.progress = progress;
  message.currentProgress = formatProgress(progress);
  return true;
}

export function formatProgress(progress: AgentProgress): string {
  if (progress.status === "failed") {
    return "当前阶段执行失败…";
  }
  if (progress.phase === "retrieval") {
    if (progress.status === "completed") {
      return `已找到 ${progress.result_count ?? 0} 条资料，正在检查证据…`;
    }
    return progress.collection ? `正在检索 ${progress.collection}…` : "正在检索知识库…";
  }
  const labels: Record<AgentProgress["phase"], { running: string; completed: string }> = {
    memory: { running: "正在读取会话记忆…", completed: "会话记忆已就绪…" },
    planning: { running: "正在生成执行计划…", completed: "执行计划已生成…" },
    evidence: { running: "正在检查证据完整性…", completed: "证据检查已完成…" },
    context: { running: "正在整理回答上下文…", completed: "回答上下文已就绪…" },
    answer: { running: "正在生成回答…", completed: "回答已生成，正在收尾…" },
    memory_write: { running: "正在保存会话记忆…", completed: "会话记忆已保存…" },
    retrieval: { running: "正在检索知识库…", completed: "检索已完成…" },
  };
  return labels[progress.phase][progress.status];
}

export function reconcileAssistantMessage(message: ConsoleMessage, result: ProductionAskResponse) {
  const assistant = result.agent_response;
  if (!assistant) {
    return;
  }
  message.text = assistant.answer;
  message.sources = assistant.sources;
  message.run = result;
  message.isStreaming = false;
  message.streamError = undefined;
  message.currentProgress = undefined;
  message.summary = {
    collection: assistant.collection,
    retrievalResultCount: result.run.metrics?.retrieval_result_count ?? 0,
    durationMs: result.run.timing.duration_ms,
    ttftMs: assistant.answer_stream?.llm_ttft_ms ?? null,
    memorySaved: assistant.memory_write.saved,
  };
}

export function markStreamError(message: ConsoleMessage, error: string) {
  message.isStreaming = false;
  message.streamError = error;
  if (!message.text) {
    message.role = "error";
    message.text = error;
  }
}

export function buildAgentAskPayload(
  question: string,
  conversationId: string,
  options: AgentOptions,
): AgentAskPayload {
  return {
    question,
    conversation_id: conversationId,
    collection: options.collection.trim() || null,
    memory_window: options.memoryWindow,
    memory_compaction_enabled: options.memoryCompactionEnabled,
    memory_compaction_trigger_turns: options.memoryCompactionTriggerTurns,
    memory_compaction_trigger_tokens: options.memoryCompactionTriggerTokens,
    top_k: options.topK,
    mode: options.mode,
    filters: null,
    max_steps: options.maxSteps,
    max_retries: options.maxRetries,
    context_max_chunks: options.contextMaxChunks,
    context_token_budget: options.contextTokenBudget,
  };
}

function newSession(id: string): ConsoleSession {
  return {
    id,
    title: "新会话",
    updatedAt: new Date().toISOString(),
    messages: [],
  };
}

function createConversationId(): string {
  const suffix = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID().slice(0, 8)
    : Math.random().toString(16).slice(2, 10);
  return `conv_web_${suffix}`;
}

function createMessage(
  role: ConsoleMessage["role"],
  text: string,
  createdAt = new Date().toISOString(),
  sources: string[] = [],
  run?: ProductionAskResponse,
): ConsoleMessage {
  return {
    id: `msg_${createdAt}_${Math.random().toString(16).slice(2, 8)}`,
    role,
    text,
    createdAt,
    sources,
    run,
  };
}

function appendMessage(session: ConsoleSession, message: ConsoleMessage) {
  session.messages = [...session.messages, message].slice(-MAX_MESSAGES_PER_SESSION);
}

function getSessionFrom(sessions: ConsoleSession[], conversationId: string): ConsoleSession | undefined {
  return sessions.find((session) => session.id === conversationId);
}

function latestSessionRun(session: ConsoleSession | undefined): ProductionAskResponse | null {
  if (!session) {
    return null;
  }
  const run = [...session.messages].reverse().find((message) => message.run)?.run;
  return run ? normalizeProductionResponse(run) : null;
}

function compactTitle(question: string): string {
  return question.length > 28 ? `${question.slice(0, 28)}...` : question;
}

function loadSessions(): ConsoleSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const value = JSON.parse(raw) as ConsoleSession[];
    return Array.isArray(value) ? value.slice(0, MAX_SESSIONS) : [];
  } catch {
    return [];
  }
}

function saveSessions(sessions: ConsoleSession[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.slice(0, MAX_SESSIONS)));
  } catch {
    // 浏览器的存储额度不足不影响当前会话继续运行。
  }
}
