import type {
  AgentStreamEvent,
  AgentAskPayload,
  ConsoleConversationResponse,
  ProductionAskResponse,
  RunRecord,
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

export async function askAgent(payload: AgentAskPayload): Promise<ProductionAskResponse> {
  return request<ProductionAskResponse>("/agent/ask", {
    method: "POST",
    body: JSON.stringify(payload),
  });
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

export async function fetchHealth(): Promise<{ status: string; version: string }> {
  return request<{ status: string; version: string }>("/health");
}

export async function fetchRuns(limit = 12): Promise<RunRecord[]> {
  return request<RunRecord[]>(`/runs?limit=${limit}`);
}

export async function fetchConversation(
  conversationId: string,
  window: number,
): Promise<ConsoleConversationResponse> {
  return request<ConsoleConversationResponse>(
    `/console/conversations/${encodeURIComponent(conversationId)}?window=${window}`,
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
