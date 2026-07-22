import type {
  AgentStreamEvent,
  AgentAskPayload,
  ConsoleConfigResponse,
  ConsoleConversationDeleteResponse,
  ConsoleConversationListResponse,
  ConsoleConversationResponse,
  McpRuntimeResponse,
  CollectionRuntimeResponse,
  ProductionAskResponse,
  RunRecord,
  SkillRuntimeResponse,
  SandboxRuntimeConfigResponse,
} from "@/types/production";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class ConsoleContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConsoleContractError";
  }
}

export async function fetchConsoleConfig(): Promise<ConsoleConfigResponse> {
  return parseConsoleConfig(await request<unknown>("/console/config"));
}

export function parseConsoleConfig(payload: unknown): ConsoleConfigResponse {
  if (!isRecord(payload)) {
    throw new ConsoleContractError("后端未返回有效的 Console 配置。");
  }
  if (payload.contract_version !== "console.v1") {
    const detected = typeof payload.contract_version === "string" ? payload.contract_version : "未提供";
    throw new ConsoleContractError(`后端 Console 契约不兼容：需要 console.v1，当前为 ${detected}。`);
  }
  const features = payload.features;
  const endpoints = payload.endpoints;
  if (!isRecord(features) || !isRecord(endpoints)) {
    throw new ConsoleContractError("后端 console.v1 配置缺少 features 或 endpoints。");
  }
  const requiredFeatures = [
    "sse",
    "answer_delta",
    "conversation_memory",
    "conversation_management",
    "collections",
  ] as const;
  const missingFeatures = requiredFeatures.filter((key) => features[key] !== true);
  if (missingFeatures.length > 0) {
    throw new ConsoleContractError(`后端 console.v1 缺少当前页面所需能力：${missingFeatures.join(", ")}。`);
  }
  const requiredEndpoints = ["ask", "stream", "conversations", "conversation", "runs"] as const;
  if (requiredEndpoints.some((key) => typeof endpoints[key] !== "string")) {
    throw new ConsoleContractError("后端 console.v1 配置缺少必要 endpoint。");
  }
  return payload as unknown as ConsoleConfigResponse;
}

export async function askAgent(payload: AgentAskPayload): Promise<ProductionAskResponse> {
  const response = await request<ProductionAskResponse>("/agent/ask", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return normalizeProductionResponse(response);
}

export async function streamAgent(
  payload: AgentAskPayload,
  onEvent: (event: AgentStreamEvent) => void,
): Promise<ProductionAskResponse> {
  const response = await fetch(`${API_BASE}/agent/ask/stream`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      "Cache-Control": "no-cache",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response));
  }
  if (!response.body) {
    throw new Error("SSE 响应没有可读取的 body。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResponse: ProductionAskResponse | null = null;

  const consume = (frame: string) => {
    const lines = frame.split(/\r?\n/);
    const eventName = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
    const data = lines
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!data) {
      return;
    }
    const event = JSON.parse(data) as AgentStreamEvent;
    if (eventName) {
      event.name = eventName;
    }
    if (event.data.response) {
      event.data.response = normalizeProductionResponse(event.data.response);
    }
    onEvent(event);
    if (event.data.response) {
      finalResponse = event.data.response;
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      consume(frame);
    }
    if (done) {
      break;
    }
  }
  if (buffer.trim()) {
    consume(buffer);
  }
  if (!finalResponse) {
    throw new Error("SSE 流结束时没有收到最终 Agent 响应。");
  }
  return finalResponse;
}

export function normalizeProductionResponse(response: ProductionAskResponse): ProductionAskResponse {
  const agent = response.agent_response ?? response.skill_result?.agent_response ?? null;
  if (agent?.skill_selection) {
    const selection = agent.skill_selection;
    selection.selected_skills = selection.selected_skills?.length
      ? selection.selected_skills
      : selection.selected_skill ? [selection.selected_skill] : [];
    selection.explicit_skills = selection.explicit_skills ?? [];
    selection.implicit_skills = selection.implicit_skills ?? [];
    selection.candidates = selection.candidates ?? [];
    selection.routing_decision = selection.routing_decision ?? null;
    selection.router_called = selection.router_called ?? false;
  }
  if (agent) {
    agent.loaded_skills = agent.loaded_skills?.length
      ? agent.loaded_skills
      : agent.loaded_skill ? [agent.loaded_skill] : [];
  }
  return {
    ...response,
    agent_response: agent,
  };
}

export async function fetchHealth(): Promise<{ status: string; version: string }> {
  return request<{ status: string; version: string }>("/health");
}

export async function fetchRuns(limit = 12): Promise<RunRecord[]> {
  return request<RunRecord[]>(`/runs?limit=${limit}`);
}

export async function fetchMcpRuntime(path = "/mcp/runtime"): Promise<McpRuntimeResponse> {
  return request<McpRuntimeResponse>(path);
}

export async function fetchCollectionRuntime(path = "/collections/runtime"): Promise<CollectionRuntimeResponse> {
  return request<CollectionRuntimeResponse>(path);
}

export async function fetchSkillRuntime(path = "/skills/runtime"): Promise<SkillRuntimeResponse> {
  return request<SkillRuntimeResponse>(path);
}

export async function fetchSandboxRuntime(path = "/sandbox/runtime"): Promise<SandboxRuntimeConfigResponse> {
  return request<SandboxRuntimeConfigResponse>(path);
}

export async function fetchConversation(
  conversationId: string,
  window: number,
): Promise<ConsoleConversationResponse> {
  return request<ConsoleConversationResponse>(
    `/console/conversations/${encodeURIComponent(conversationId)}?window=${window}`,
  );
}

export async function fetchConversations(limit = 50): Promise<ConsoleConversationListResponse> {
  return request<ConsoleConversationListResponse>(`/console/conversations?limit=${limit}`);
}

export async function deleteConversation(
  conversationId: string,
): Promise<ConsoleConversationDeleteResponse> {
  return request<ConsoleConversationDeleteResponse>(
    `/console/conversations/${encodeURIComponent(conversationId)}`,
    { method: "DELETE" },
  );
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
    ...init,
  });
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response));
  }
  return (await response.json()) as T;
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail || `请求失败 (${response.status})`;
  } catch {
    return `请求失败 (${response.status})`;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
