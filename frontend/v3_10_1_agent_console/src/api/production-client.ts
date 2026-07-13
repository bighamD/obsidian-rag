import type {
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
