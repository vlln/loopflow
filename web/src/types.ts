export type RunStatus = 'running' | 'done' | 'failed' | 'stopped' | 'stale' | 'unreadable';

export interface RunSummary {
  run_id: string;
  loop: string | null;
  status: RunStatus;
  current_phase: string | null;
  created: string | null;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string | null;
  duration_ms: number | null;
  iteration_count: number;
  error_summary: string | null;
  parse_error: string | null;
  allowed_actions: string[];
}

export interface PhaseNode { phase: string; occurrence_count: number; is_current: boolean }
export interface PhaseEdge { from: string; to: string; count: number; is_backedge: boolean }
export interface Occurrence { phase_id: string; phase: string; occurrence: number; started_at: string | null; ended_at: string | null; call_ids: string[] }
export interface AgentCall { call_id: string; phase_id: string; session: string | null; status: string; started_at: string | null; finished_at: string | null; exit_code: number | null; backend: string | null; model: string | null }
export interface RunEvent { version?: number; event_id?: number; type: string; ts?: string; phase?: string; phase_id?: string; call_id?: string; payload?: Record<string, unknown>; [key: string]: unknown }

export interface RunDetail extends RunSummary {
  args: Record<string, unknown> | null;
  state: Record<string, unknown> | null;
  working_directory: string;
  graph: { nodes: PhaseNode[]; edges: PhaseEdge[]; current_phase_id: string | null };
  occurrences: Occurrence[];
  calls: AgentCall[];
  unattributed_count: number;
  malformed_count: number;
  events: RunEvent[];
  unattributed: RunEvent[];
  malformed: RunEvent[];
}

export interface LoopSummary { name: string; description: string; agent_count: number; triggers: unknown[]; valid: boolean; error_summary: string | null }
export interface LoopFile { path: string; media_type: string | null; size: number; previewable: boolean }
export interface LoopDetail { name: string; description: string; valid: boolean; error_summary: string | null; triggers: unknown[]; resources: unknown[]; environment: string | null; files: LoopFile[]; agents: { name: string; description: string; path: string }[]; runs: RunSummary[] }
export interface Backend { name: string; status: string; reason: string | null; cli_path: string | null; version: string | null; transport: string; capabilities: Record<string, boolean>; diagnosed_at: string | null }
export interface Diagnostic { name: string; status: string; reason: string | null; exit_code: number | null; stdout: string; stderr: string; diagnosed_at: string }

export interface Page<T> { items: T[]; next_cursor: string | null }
