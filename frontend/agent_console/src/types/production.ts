export type SearchMode = "dense" | "keyword" | "hybrid";
export type RunStatus = "queued" | "running" | "succeeded" | "failed";
export type PermissionProfile = "standard" | "knowledge_only" | "restricted" | "sandbox";
export type AgentProgressPhase =
  | "memory"
  | "skill"
  | "planning"
  | "routing"
  | "authorization"
  | "retrieval"
  | "evidence"
  | "context"
  | "answer"
  | "memory_write";

export interface AgentProgress {
  phase: AgentProgressPhase;
  status: "running" | "completed" | "failed";
  collection?: string | null;
  result_count?: number | null;
  metadata?: Record<string, unknown>;
}

export interface AgentOptions {
  mcpEnabled: boolean;
  permissionProfile: PermissionProfile;
  skillRouterEnabled: boolean;
  skillNames: string[];
  skillSelectionMode: "augment" | "exclusive";
  sandboxEnabled: boolean;
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
  mcp_enabled: boolean;
  principal: PermissionPrincipal;
  skill_router_enabled: boolean;
  skill_name: string | null;
  skill_names: string[];
  skill_selection_mode: "augment" | "exclusive";
  sandbox_enabled: boolean;
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
    message_id?: string;
    sequence?: number;
    delta?: string;
    node_name?: string;
    run?: RunRecord;
    response?: ProductionAskResponse;
    agent?: {
      phase?: AgentProgressPhase;
      status?: AgentProgress["status"] | "success" | "skipped";
      collection?: string | null;
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
      source?: string | null;
      argument_names?: string[];
      error?: string | null;
      metadata?: Record<string, unknown>;
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
  arguments: Record<string, unknown>;
  instruction: string | null;
  status: "success" | "skipped" | "failed";
  result_count: number;
  results: SearchHit[];
  sources: string[];
  error: string | null;
  reason: string | null;
  observation: ToolObservation | null;
  metadata: Record<string, unknown>;
}

export interface PlanStep {
  id: string;
  kind: string;
  query: string | null;
  tool_name: string | null;
  arguments: Record<string, unknown>;
  instruction: string | null;
  depends_on: string[];
  reason: string | null;
}

export interface ToolObservation {
  step_id: string;
  tool_name: string;
  source: string;
  status: "success" | "skipped" | "failed";
  data: unknown;
  summary: string;
  metadata: Record<string, unknown>;
  error: string | null;
}

export interface PlannerToolDefinition {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  source: string;
  read_only: boolean | null;
}

export interface PermissionPrincipal {
  subject_id: string;
  roles: string[];
  permissions: string[];
  tool_allowlist: string[];
  allowed_collections: string[];
}

export interface PermissionDecision {
  step_id: string;
  kind: string;
  tool_name: string | null;
  source: string;
  risk_level: "safe" | "confirm" | "restricted";
  decision: "allow" | "confirm" | "deny";
  reason: string;
  required_permissions: string[];
  missing_permissions: string[];
  collections: string[];
  denied_collections: string[];
  argument_names: string[];
  validation_errors: string[];
}

export interface PermissionReport {
  principal: PermissionPrincipal;
  decisions: PermissionDecision[];
  allow_count: number;
  confirm_count: number;
  deny_count: number;
  all_allowed: boolean;
  summary: string;
}

export interface AgentTraceStep {
  node_name: string;
  step_type: string;
  step_id: string | null;
  tool_name: string | null;
  query: string | null;
  result_count: number | null;
  reason: string | null;
  metadata: Record<string, unknown>;
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
  collection: string;
  answer: string;
  used_retrieval: boolean;
  sources: string[];
  plan: { goal: string; steps: PlanStep[] };
  tool_catalog: PlannerToolDefinition[];
  retrieval_scope: RetrievalScope | null;
  permission_report: PermissionReport | null;
  skill_selection: SkillSelection | null;
  loaded_skill: SkillLoadedSummary | null;
  loaded_skills: SkillLoadedSummary[];
  sandbox_workspace_id: string | null;
  sandbox_artifacts: ArtifactRecord[];
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
    tool_observations: ToolObservation[];
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
  answer_stream: {
    mode: "complete" | "stream" | "fallback";
    message_id: string | null;
    llm_ttft_ms: number | null;
    llm_reasoning_ttft_ms: number | null;
    llm_generation_ms: number;
    visible_character_count: number;
    reasoning_character_count: number;
  };
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

export interface SkillManifest {
  name: string;
  description: string;
  triggers: string[];
  version: string;
  entry_file: string;
  path: string;
}

export interface SkillSelection {
  status: "selected" | "forced" | "no_skill" | "disabled" | "invalid_selection" | "router_error";
  selected_skill: string | null;
  selected_skills: string[];
  explicit_skills: string[];
  implicit_skills: string[];
  reason: string;
  confidence: number | null;
  candidate_names: string[];
  candidates: SkillCandidate[];
  routing_decision: SkillRoutingDecision | null;
  router_called: boolean;
}

export interface SkillCandidate {
  name: string;
  score: number;
  bm25_score: number;
  overlap_score: number;
  trigger_score: number;
  matched_triggers: string[];
}

export interface SkillRoutingDecision {
  path: "no_skill" | "direct" | "llm_router" | "explicit_only" | "disabled";
  selected_skill_names: string[];
  reason: string;
  top_score: number | null;
  score_margin: number | null;
}

export interface SkillLoadedSummary extends SkillManifest {
  estimated_tokens: number;
}

export interface SkillRuntimeResponse {
  root: string;
  skills: SkillManifest[];
  errors: string[];
}

export interface ArtifactRecord {
  artifact_id: string;
  run_id: string;
  relative_path: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
}

export interface SandboxProfile {
  name: string;
  image: string;
  network_disabled: boolean;
  read_only_root: boolean;
  timeout_seconds: number;
  max_output_bytes: number;
  max_file_bytes: number;
  memory_mb: number;
  cpus: number;
  pids_limit: number;
  allowed_commands: string[];
}

export interface SandboxRuntimeStatus {
  backend: "docker";
  available: boolean;
  docker_version: string | null;
  workspace_root: string;
  profile: SandboxProfile;
  error: string | null;
}

export interface SandboxRuntimeConfigResponse {
  version: "v3.14";
  json_endpoint: string;
  stream_endpoint: string;
  sandbox_call_endpoint: string;
  artifacts_endpoint: string;
  sandbox: SandboxRuntimeStatus;
  permission_policy_enabled: boolean;
  skill_router_enabled: boolean;
  approval_resume_enabled: boolean;
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

export interface ConsoleConversationSummary {
  conversation_id: string;
  title: string;
  turn_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConsoleConversationListResponse {
  conversations: ConsoleConversationSummary[];
}

export interface ConsoleConversationDeleteResponse {
  conversation_id: string;
  deleted: boolean;
  deleted_turn_count: number;
}

export interface ConsoleConfigResponse {
  contract_version: string;
  backend_version: string;
  features: {
    json: boolean;
    sse: boolean;
    answer_delta: boolean;
    reasoning_delta: boolean;
    conversation_memory: boolean;
    conversation_management: boolean;
    collections: boolean;
    mcp_tools?: boolean;
    collection_routing?: boolean;
    permission_policy?: boolean;
    skills?: boolean;
    sandbox?: boolean;
  };
  endpoints: {
    ask: string;
    stream: string;
    conversations: string;
    conversation: string;
    runs: string;
    mcp_runtime?: string | null;
    collection_runtime?: string | null;
    skills_runtime?: string | null;
    sandbox_runtime?: string | null;
    sandbox_artifacts?: string | null;
  };
  default_memory_window: number;
}

export type ConsoleCompatibilityStatus = "checking" | "compatible" | "incompatible" | "unavailable";

export interface McpServerRuntime {
  name: string;
  description: string;
  transport: "stdio" | "streamable_http";
  status: "disconnected" | "connecting" | "connected" | "degraded" | "failed";
  protocol_version: string | null;
  tool_count: number;
  tool_names: string[];
  connected_at: string | null;
  discovered_at: string | null;
  call_count: number;
  failure_count: number;
  last_error: string | null;
}

export interface McpToolDefinition {
  server_name: string;
  name: string;
  namespaced_name: string;
  title: string | null;
  description: string | null;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown> | null;
  read_only: boolean | null;
}

export interface McpRuntimeResponse {
  registry_path: string;
  started: boolean;
  servers: McpServerRuntime[];
  tools: McpToolDefinition[];
  errors: Record<string, string>;
}

export interface McpLiveToolEvent {
  stepId: string;
  toolName: string;
  source: string;
  status: "running" | "success" | "failed";
  durationMs: number | null;
  error: string | null;
}

export interface KnowledgeBaseManifest {
  id: string;
  collection: string;
  description: string;
  triggers: string[];
  enabled: boolean;
}

export interface RetrievalScope {
  status: "not_required" | "explicit" | "disabled" | "selected" | "multi_selected" | "no_collection" | "invalid_selection" | "router_error";
  selected_ids: string[];
  selected_collections: string[];
  candidate_ids: string[];
  reason: string;
  confidence: number | null;
  registry_path: string | null;
  errors: Record<string, string>;
}

export interface CollectionRuntimeResponse {
  registry_path: string;
  knowledge_bases: KnowledgeBaseManifest[];
  enabled_ids: string[];
  errors: string[];
}

export interface ConsoleSession {
  id: string;
  title: string;
  updatedAt: string;
  persisted: boolean;
  messages: ConsoleMessage[];
}

export interface ConsoleMessage {
  id: string;
  role: "user" | "assistant" | "error";
  text: string;
  createdAt: string;
  sources?: string[];
  run?: ProductionAskResponse;
  streamMessageId?: string;
  streamSequence?: number;
  reasoningMessageId?: string;
  reasoningSequence?: number;
  reasoningText?: string;
  isStreaming?: boolean;
  streamError?: string;
  progress?: AgentProgress;
  currentProgress?: string;
  summary?: {
    collection: string;
    retrievalResultCount: number;
    durationMs: number | null;
    ttftMs: number | null;
    memorySaved: boolean;
  };
}
