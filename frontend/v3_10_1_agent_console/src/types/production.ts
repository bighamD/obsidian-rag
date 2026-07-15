export type SearchMode = "dense" | "keyword" | "hybrid";
export type RunStatus = "queued" | "running" | "succeeded" | "failed";

export interface AgentOptions {
  memoryWindow: number;
  memoryCompactionEnabled: boolean;
  memoryCompactionTriggerTurns: number;
  memoryCompactionTriggerTokens: number;
  topK: number;
  mode: SearchMode;
  maxSteps: number;
  maxRetries: number;
  contextMaxChunks: number;
  contextTokenBudget: number;
}

export interface AgentAskPayload {
  question: string;
  conversation_id: string;
  memory_window: number;
  memory_compaction_enabled: boolean;
  memory_compaction_trigger_turns: number;
  memory_compaction_trigger_tokens: number;
  top_k: number;
  mode: SearchMode;
  filters: null;
  max_steps: number;
  max_retries: number;
  context_max_chunks: number;
  context_token_budget: number;
}

export interface RunEvent {
  name: string;
  status: RunStatus;
  occurred_at: string;
  detail: string;
}

export interface AgentStreamEvent {
  event_id: number;
  run_id: string;
  name: string;
  status: RunStatus;
  occurred_at: string;
  detail: string;
  data: {
    run?: RunRecord;
    response?: ProductionAskResponse;
    agent?: {
      node_name?: string;
      step_type?: string;
      step_id?: string | null;
      tool_name?: string | null;
      query?: string | null;
      result_count?: number | null;
      reason?: string | null;
      started_at?: string | null;
      finished_at?: string | null;
      duration_ms?: number | null;
    };
  };
}

export interface ToolRunSummary {
  tool_name: string;
  call_count: number;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  result_count: number;
}

export interface RunMetrics {
  timing: { started_at: string; finished_at: string | null; duration_ms: number | null };
  token_estimate: {
    answer_prompt_tokens: number;
    answer_output_tokens: number;
    observed_total_tokens: number;
    method: string;
  };
  graph_node_count: number;
  trace_event_count: number;
  node_timings: AgentNodeTiming[];
  retrieval_result_count: number;
  tool_summaries: ToolRunSummary[];
}

export interface AgentNodeTiming {
  node_name: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
}

export interface RunRecord {
  run_id: string;
  status: RunStatus;
  agent_run_id: string | null;
  conversation_id: string | null;
  timing: { started_at: string; finished_at: string | null; duration_ms: number | null };
  events: RunEvent[];
  metrics: RunMetrics | null;
  error: { error_type: string; message: string; retryable: boolean } | null;
}

export interface SearchHit {
  chunk_id: string | null;
  source: string;
  topic: string | null;
  score: number;
  dense_rank: number | null;
  keyword_rank: number | null;
  dense_score: number | null;
  keyword_score: number | null;
  hybrid_score: number | null;
  text_preview: string;
  text: string | null;
  metadata: Record<string, unknown>;
}

export interface ContextChunk extends SearchHit {
  step_id: string | null;
  reason: string | null;
}

export interface StepResult {
  step_id: string;
  kind: string;
  tool_name: string | null;
  query: string | null;
  instruction: string | null;
  status: "success" | "skipped" | "failed";
  result_count: number;
  results: SearchHit[];
  sources: string[];
  error: string | null;
  reason: string | null;
}

export interface PlanStep {
  id: string;
  kind: string;
  query: string | null;
  instruction: string | null;
  depends_on: string[];
  reason: string | null;
}

export interface AgentTraceStep {
  node_name: string;
  step_type: string;
  step_id: string | null;
  tool_name: string | null;
  query: string | null;
  result_count: number | null;
  reason: string | null;
}

export interface MemoryTurn {
  turn_id: string;
  user_message: string;
  assistant_message: string;
  sources: string[];
  created_at: string;
}

export interface MemorySnapshot {
  conversation_id: string;
  window: number;
  recent_turns: MemoryTurn[];
  total_turn_count: number;
  loaded_turn_count: number;
  omitted_turn_count: number;
  summary_text: string;
  summary_through_turn_id: string | null;
}

export interface AgentResponse {
  run_id: string;
  conversation_id: string;
  question: string;
  answer: string;
  used_retrieval: boolean;
  sources: string[];
  plan: { goal: string; steps: PlanStep[] };
  step_results: StepResult[];
  retry_step_results: StepResult[];
  evidence_check: {
    is_sufficient: boolean;
    missing_points: string[];
    suggested_queries: string[];
    checked_step_ids: string[];
    missing_step_ids: string[];
    retry_count: number;
    reason: string;
  };
  context_bundle: {
    included_chunks: ContextChunk[];
    excluded_chunks: ContextChunk[];
    token_budget: number;
    context_summary: string;
  };
  memory_snapshot: MemorySnapshot;
  memory_compaction: {
    compacted: boolean;
    attempted: boolean;
    summarized_turn_count: number;
    reason: string;
  };
  memory_write: { saved: boolean; turn_id: string | null; reason: string | null };
  graph_path: string[];
  trace: AgentTraceStep[];
}

export interface SkillAgentResult {
  agent_response: AgentResponse;
  skill_selection: Record<string, unknown>;
  loaded_skill: Record<string, unknown> | null;
  graph_path: string[];
  trace: Record<string, unknown>[];
}

export interface ProductionAskResponse {
  run: RunRecord;
  agent_response: AgentResponse | null;
  skill_result?: SkillAgentResult | null;
}

export interface ConsoleConversationResponse {
  conversation_id: string;
  memory_snapshot: MemorySnapshot;
}

export interface ConsoleSession {
  id: string;
  title: string;
  updatedAt: string;
  messages: ConsoleMessage[];
}

export interface ConsoleMessage {
  id: string;
  role: "user" | "assistant" | "error";
  text: string;
  createdAt: string;
  sources?: string[];
  run?: ProductionAskResponse;
}
