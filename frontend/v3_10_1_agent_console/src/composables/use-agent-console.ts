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
    session.title = compactTitle(trimmedQuestion);
    session.updatedAt = new Date().toISOString();
    isRunning.value = true;
    response.value = null;
    requestError.value = "";

    try {
      const result = await streamAgent(
        toPayload(trimmedQuestion, activeConversationId.value, options),
        (event) => applyStreamEvent(event),
      );
      response.value = result;
      const assistant = result.agent_response;
      if (assistant) {
        appendMessage(
          session,
          createMessage("assistant", assistant.answer, undefined, assistant.sources, result),
        );
        memorySnapshot.value = assistant.memory_snapshot;
      } else {
        appendMessage(
          session,
          createMessage("error", result.run.error?.message ?? "本次运行没有生成可展示的答案。", undefined, [], result),
        );
      }
      await refreshRuns();
    } catch (error) {
      const message = error instanceof Error ? error.message : "请求失败。";
      requestError.value = message;
      appendMessage(session, createMessage("error", message));
    } finally {
      isRunning.value = false;
      session.updatedAt = new Date().toISOString();
    }
  }

  function applyStreamEvent(event: AgentStreamEvent) {
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

function toPayload(question: string, conversationId: string, options: AgentOptions): AgentAskPayload {
  return {
    question,
    conversation_id: conversationId,
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
