import { computed, onMounted, reactive, ref } from "vue";

import {
  ConsoleContractError,
  deleteConversation as deleteConversationRequest,
  fetchConversation,
  fetchCollectionRuntime,
  fetchConsoleConfig,
  fetchConversations,
  fetchHealth,
  fetchMcpRuntime,
  fetchRuns,
  fetchSkillRuntime,
  fetchSandboxRuntime,
  normalizeProductionResponse,
  streamAgent,
} from "@/api/production-client";
import type {
  AgentStreamEvent,
  AgentAskPayload,
  AgentOptions,
  AgentProgress,
  ConsoleCompatibilityStatus,
  ConsoleConfigResponse,
  ConsoleConversationSummary,
  ConsoleMessage,
  CollectionRuntimeResponse,
  ConsoleSession,
  MemorySnapshot,
  McpLiveToolEvent,
  McpRuntimeResponse,
  ProductionAskResponse,
  RunRecord,
  SkillRuntimeResponse,
  SandboxRuntimeConfigResponse,
} from "@/types/production";

const MAX_SESSIONS = 50;
const MAX_MESSAGES_PER_SESSION = 40;
const DISPLAY_HISTORY_WINDOW = 20;

const defaultOptions: AgentOptions = {
  collection: "",
  collectionRouterEnabled: true,
  maxCollections: 2,
  mcpEnabled: true,
  permissionProfile: "standard",
  skillRouterEnabled: true,
  skillNames: [],
  skillSelectionMode: "augment",
  sandboxEnabled: true,
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
  const initialConversationId = createConversationId();
  const sessions = ref<ConsoleSession[]>([newSession(initialConversationId)]);
  const activeConversationId = ref(initialConversationId);
  const response = ref<ProductionAskResponse | null>(null);
  const recentRuns = ref<RunRecord[]>([]);
  const memorySnapshot = ref<MemorySnapshot | null>(null);
  const isRunning = ref(false);
  const apiOnline = ref<boolean | null>(null);
  const consoleConfig = ref<ConsoleConfigResponse | null>(null);
  const compatibilityStatus = ref<ConsoleCompatibilityStatus>("checking");
  const compatibilityError = ref("");
  const requestError = ref("");
  const mcpRuntime = ref<McpRuntimeResponse | null>(null);
  const collectionRuntime = ref<CollectionRuntimeResponse | null>(null);
  const skillRuntime = ref<SkillRuntimeResponse | null>(null);
  const sandboxRuntime = ref<SandboxRuntimeConfigResponse | null>(null);
  const liveToolEvents = ref<McpLiveToolEvent[]>([]);
  const deletingConversationId = ref<string | null>(null);
  const options = reactive<AgentOptions>({ ...defaultOptions });

  const activeSession = computed(
    () => sessions.value.find((session) => session.id === activeConversationId.value) ?? sessions.value[0],
  );
  const isConsoleCompatible = computed(() => compatibilityStatus.value === "compatible");

  onMounted(async () => {
    await loadWorkspace(true);
  });

  async function refreshWorkspace() {
    await loadWorkspace(false);
  }

  async function loadWorkspace(initial: boolean) {
    compatibilityStatus.value = "checking";
    compatibilityError.value = "";
    if (!(await refreshCompatibility())) {
      apiOnline.value = false;
      recentRuns.value = [];
      memorySnapshot.value = null;
      return;
    }
    await Promise.all([
      refreshHealth(),
      refreshRuns(),
      refreshMcpRuntime(),
      refreshCollectionRuntime(),
      refreshSkillRuntime(),
      refreshSandboxRuntime(),
    ]);
    await refreshConversationList({ initial, hydrateActive: true });
  }

  async function refreshCompatibility(): Promise<boolean> {
    try {
      consoleConfig.value = await fetchConsoleConfig();
      compatibilityStatus.value = "compatible";
      options.memoryWindow = consoleConfig.value.default_memory_window;
      return true;
    } catch (error) {
      consoleConfig.value = null;
      compatibilityStatus.value = error instanceof ConsoleContractError ? "incompatible" : "unavailable";
      compatibilityError.value = error instanceof Error
        ? error.message
        : "无法读取后端 Console 配置，请确认 API 地址和服务状态。";
      return false;
    }
  }

  async function refreshHealth() {
    try {
      const health = await fetchHealth();
      apiOnline.value = health.status === "ok" || health.status === "degraded";
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

  async function refreshMcpRuntime() {
    const path = consoleConfig.value?.features.mcp_tools
      ? consoleConfig.value.endpoints.mcp_runtime
      : null;
    if (!path) {
      mcpRuntime.value = null;
      return;
    }
    try {
      mcpRuntime.value = await fetchMcpRuntime(path);
    } catch {
      mcpRuntime.value = null;
    }
  }

  async function refreshCollectionRuntime() {
    const path = consoleConfig.value?.features.collection_routing
      ? consoleConfig.value.endpoints.collection_runtime
      : null;
    if (!path) {
      collectionRuntime.value = null;
      return;
    }
    try {
      collectionRuntime.value = await fetchCollectionRuntime(path);
    } catch {
      collectionRuntime.value = null;
    }
  }

  async function refreshSkillRuntime() {
    const path = consoleConfig.value?.features.skills
      ? consoleConfig.value.endpoints.skills_runtime
      : null;
    if (!path) {
      skillRuntime.value = null;
      return;
    }
    try {
      skillRuntime.value = await fetchSkillRuntime(path);
    } catch {
      skillRuntime.value = null;
    }
  }

  async function refreshSandboxRuntime() {
    const path = consoleConfig.value?.features.sandbox
      ? consoleConfig.value.endpoints.sandbox_runtime
      : null;
    if (!path) {
      sandboxRuntime.value = null;
      return;
    }
    try {
      sandboxRuntime.value = await fetchSandboxRuntime(path);
    } catch {
      sandboxRuntime.value = null;
    }
  }

  async function refreshConversationList(
    settings: { initial?: boolean; hydrateActive?: boolean } = {},
  ): Promise<boolean> {
    try {
      const result = await fetchConversations(MAX_SESSIONS);
      const existingById = new Map(sessions.value.map((session) => [session.id, session]));
      const persisted = result.conversations.map((summary) => persistedSession(summary, existingById.get(summary.conversation_id)));

      if (settings.initial) {
        sessions.value = persisted.length > 0 ? persisted : [newSession(activeConversationId.value)];
        activeConversationId.value = sessions.value[0].id;
      } else {
        const persistedIds = new Set(persisted.map((session) => session.id));
        const temporary = sessions.value.filter(
          (session) => !session.persisted && !persistedIds.has(session.id),
        );
        sessions.value = [...temporary, ...persisted].slice(0, MAX_SESSIONS);
        if (sessions.value.length === 0) {
          const session = newSession(createConversationId());
          sessions.value = [session];
          activeConversationId.value = session.id;
        } else if (!getSessionFrom(sessions.value, activeConversationId.value)) {
          activeConversationId.value = sessions.value[0].id;
        }
      }

      if (settings.hydrateActive) {
        await hydrateConversation(activeConversationId.value);
      }
      return true;
    } catch (error) {
      requestError.value = error instanceof Error ? error.message : "会话历史加载失败。";
      return false;
    }
  }

  async function hydrateConversation(conversationId: string) {
    const session = getSessionFrom(sessions.value, conversationId);
    response.value = latestSessionRun(session);
    if (!session?.persisted) {
      memorySnapshot.value = null;
      return;
    }
    try {
      const conversation = await fetchConversation(conversationId, DISPLAY_HISTORY_WINDOW);
      memorySnapshot.value = conversation.memory_snapshot;
      session.messages = conversation.memory_snapshot.recent_turns.flatMap((turn) => [
        createMessage("user", turn.user_message, turn.created_at),
        createMessage("assistant", turn.assistant_message, turn.created_at, turn.sources),
      ]);
    } catch {
      memorySnapshot.value = null;
    }
  }

  async function selectConversation(conversationId: string) {
    if (!isConsoleCompatible.value) {
      requestError.value = compatibilityError.value;
      return;
    }
    activeConversationId.value = conversationId;
    requestError.value = "";
    await hydrateConversation(conversationId);
  }

  function createConversation() {
    const session = newSession(createConversationId());
    sessions.value = [session, ...sessions.value].slice(0, MAX_SESSIONS);
    activeConversationId.value = session.id;
    response.value = null;
    liveToolEvents.value = [];
    memorySnapshot.value = null;
    requestError.value = "";
  }

  async function deleteConversation(conversationId: string) {
    if (isRunning.value || deletingConversationId.value) {
      return;
    }
    const session = getSessionFrom(sessions.value, conversationId);
    if (!session) {
      return;
    }

    deletingConversationId.value = conversationId;
    requestError.value = "";
    try {
      if (session.persisted) {
        await deleteConversationRequest(conversationId);
      }
      const wasActive = activeConversationId.value === conversationId;
      sessions.value = sessions.value.filter((item) => item.id !== conversationId);
      if (sessions.value.length === 0) {
        const replacement = newSession(createConversationId());
        sessions.value = [replacement];
      }
      if (wasActive) {
        const replacement = sessions.value.find((item) => item.persisted) ?? sessions.value[0];
        activeConversationId.value = replacement.id;
        response.value = null;
        memorySnapshot.value = null;
        await hydrateConversation(activeConversationId.value);
      }
    } catch (error) {
      requestError.value = error instanceof Error ? error.message : "删除会话失败。";
    } finally {
      deletingConversationId.value = null;
    }
  }

  async function submit(question: string) {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isRunning.value || !isConsoleCompatible.value) {
      if (!isConsoleCompatible.value) {
        requestError.value = compatibilityError.value;
      }
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
    liveToolEvents.value = [];
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
      await Promise.all([
        refreshRuns(),
        refreshMcpRuntime(),
        refreshCollectionRuntime(),
        refreshSkillRuntime(),
        refreshSandboxRuntime(),
        assistant?.memory_write.saved ? refreshConversationList() : Promise.resolve(false),
      ]);
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
    if (event.name === "reasoning_delta") {
      applyReasoningDelta(assistantDraft, event);
    }
    if (event.name === "tool_started" || event.name === "tool_finished") {
      applyMcpToolEvent(event);
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

  function applyMcpToolEvent(event: AgentStreamEvent) {
    const payload = event.data.agent;
    if (!payload?.tool_name) {
      return;
    }
    const stepId = payload.step_id || payload.tool_name;
    const next: McpLiveToolEvent = {
      stepId,
      toolName: payload.tool_name,
      source: payload.source || "mcp",
      status: event.name === "tool_started" ? "running" : payload.status === "success" ? "success" : "failed",
      durationMs: payload.duration_ms ?? null,
      error: payload.error ?? null,
    };
    const index = liveToolEvents.value.findIndex((item) => item.stepId === stepId && item.toolName === next.toolName);
    liveToolEvents.value = index === -1
      ? [...liveToolEvents.value, next]
      : liveToolEvents.value.map((item, itemIndex) => itemIndex === index ? next : item);
  }

  return {
    activeConversationId,
    activeSession,
    apiOnline,
    compatibilityError,
    compatibilityStatus,
    consoleConfig,
    collectionRuntime,
    createConversation,
    deleteConversation,
    deletingConversationId,
    hydrateConversation,
    isRunning,
    isConsoleCompatible,
    memorySnapshot,
    mcpRuntime,
    liveToolEvents,
    options,
    recentRuns,
    refreshConversationList,
    refreshWorkspace,
    requestError,
    response,
    sandboxRuntime,
    skillRuntime,
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
  message.reasoningSequence = 0;
  message.reasoningText = "";
  message.currentProgress = "正在生成回答…";
  return message;
}

export function applyReasoningDelta(message: ConsoleMessage, event: AgentStreamEvent): boolean {
  const { message_id: messageId, sequence, delta } = event.data;
  if (!messageId || typeof sequence !== "number" || !delta) {
    return false;
  }
  if (message.reasoningMessageId && message.reasoningMessageId !== messageId) {
    return false;
  }
  if (sequence <= (message.reasoningSequence ?? 0)) {
    return false;
  }
  message.reasoningMessageId = messageId;
  message.reasoningSequence = sequence;
  message.reasoningText = `${message.reasoningText ?? ""}${delta}`;
  return true;
}

export function applyProgressEvent(message: ConsoleMessage, event: AgentStreamEvent): boolean {
  const payload = event.data.agent;
  if (
    !payload?.phase
    || !payload.status
    || !["running", "completed", "failed"].includes(payload.status)
  ) {
    return false;
  }
  const progress: AgentProgress = {
    phase: payload.phase,
    status: payload.status as AgentProgress["status"],
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
    skill: { running: "正在选择任务方法…", completed: "任务方法已确定…" },
    planning: { running: "正在生成执行计划…", completed: "执行计划已生成…" },
    routing: { running: "正在选择知识库范围…", completed: "知识库范围已确定…" },
    authorization: { running: "正在检查步骤权限…", completed: "步骤权限已确定…" },
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
    collection_router_enabled: options.collectionRouterEnabled,
    max_collections: options.maxCollections,
    mcp_enabled: options.mcpEnabled,
    principal: principalForProfile(options.permissionProfile),
    skill_router_enabled: options.skillRouterEnabled,
    skill_name: options.skillNames[0] ?? null,
    skill_names: [...new Set(options.skillNames)],
    skill_selection_mode: options.skillSelectionMode,
    sandbox_enabled: options.sandboxEnabled,
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

function principalForProfile(profile: AgentOptions["permissionProfile"]): AgentAskPayload["principal"] {
  if (profile === "sandbox") {
    return {
      subject_id: "console_sandbox",
      roles: ["user"],
      permissions: ["knowledge.read", "tool.read", "sandbox.read", "sandbox.write", "sandbox.execute"],
      tool_allowlist: ["search_notes", "demo::*", "sandbox::*"],
      allowed_collections: ["*"],
    };
  }
  if (profile === "knowledge_only") {
    return {
      subject_id: "console_knowledge_only",
      roles: ["user"],
      permissions: ["knowledge.read"],
      tool_allowlist: ["search_notes"],
      allowed_collections: ["*"],
    };
  }
  if (profile === "restricted") {
    return {
      subject_id: "console_restricted",
      roles: ["restricted"],
      permissions: [],
      tool_allowlist: [],
      allowed_collections: [],
    };
  }
  return {
    subject_id: "console_standard",
    roles: ["user"],
    permissions: ["knowledge.read", "tool.read"],
    tool_allowlist: ["search_notes", "demo::*"],
    allowed_collections: ["*"],
  };
}

function newSession(id: string): ConsoleSession {
  return {
    id,
    title: "新会话",
    updatedAt: new Date().toISOString(),
    persisted: false,
    messages: [],
  };
}

function persistedSession(
  summary: ConsoleConversationSummary,
  existing?: ConsoleSession,
): ConsoleSession {
  return {
    id: summary.conversation_id,
    title: summary.title,
    updatedAt: summary.updated_at,
    persisted: true,
    messages: existing?.messages ?? [],
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
