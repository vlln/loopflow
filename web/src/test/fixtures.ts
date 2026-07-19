import type { Backend, LoopDetail, LoopSummary, RunDetail, RunSummary } from '../types';

export const runs: RunSummary[] = [
  { run_id: 'run-live', loop: 'review-loop', status: 'running', current_phase: 'Review', created: '2026-07-18T22:00:00Z', started_at: '2026-07-18T22:00:00Z', finished_at: null, updated_at: '2026-07-18T22:00:03Z', duration_ms: 3200, iteration_count: 1, error_summary: null, parse_error: null, allowed_actions: ['stop'] },
  { run_id: 'run-failed', loop: 'review-loop', status: 'failed', current_phase: 'Fix', created: '2026-07-18T21:00:00Z', started_at: '2026-07-18T21:00:00Z', finished_at: '2026-07-18T21:02:00Z', updated_at: '2026-07-18T21:02:00Z', duration_ms: 120000, iteration_count: 0, error_summary: 'Agent failed', parse_error: null, allowed_actions: ['resume', 'rerun'] },
  { run_id: 'run-broken', loop: null, status: 'unreadable', current_phase: null, created: null, started_at: null, finished_at: null, updated_at: null, duration_ms: null, iteration_count: 0, error_summary: null, parse_error: 'line 1, column 2: broken', allowed_actions: [] },
];

export const detail: RunDetail = {
  ...runs[0], args: {}, state: { attempt: 2 }, working_directory: '/tmp/run-live',
  graph: { nodes: [{ phase: 'Plan', occurrence_count: 1, is_current: false }, { phase: 'Review', occurrence_count: 2, is_current: true }], edges: [{ from: 'Plan', to: 'Review', count: 1, is_backedge: false }, { from: 'Review', to: 'Review', count: 1, is_backedge: true }], current_phase_id: 'review-2' },
  occurrences: [{ phase_id: 'plan-1', phase: 'Plan', occurrence: 1, started_at: '2026-07-18T22:00:00Z', ended_at: '2026-07-18T22:00:01Z', call_ids: ['call-plan'] }, { phase_id: 'review-2', phase: 'Review', occurrence: 2, started_at: '2026-07-18T22:00:02Z', ended_at: null, call_ids: ['call-a', 'call-b'] }],
  calls: [{ call_id: 'call-plan', phase_id: 'plan-1', session: 'wf-plan', status: 'done', started_at: null, finished_at: null, exit_code: 0, backend: 'kimi', model: null }, { call_id: 'call-a', phase_id: 'review-2', session: 'wf-review-a', status: 'running', started_at: null, finished_at: null, exit_code: null, backend: 'codex', model: 'gpt-5' }, { call_id: 'call-b', phase_id: 'review-2', session: 'wf-review-b', status: 'done', started_at: null, finished_at: null, exit_code: 0, backend: 'kimi', model: null }],
  unattributed_count: 1, malformed_count: 1,
  events: [{ version: 2, event_id: 1, type: 'phase', ts: '2026-07-18T22:00:00Z', phase: 'Plan', phase_id: 'plan-1', payload: {} }, { version: 2, event_id: 2, type: 'agent_start', ts: '2026-07-18T22:00:02Z', phase: 'Review', phase_id: 'review-2', call_id: 'call-a', payload: { backend: 'codex' } }],
  unattributed: [{ type: 'message', content: 'legacy' }], malformed: [{ version: 2, event_id: 3, type: 'agent_start' }],
};

export const loopSummary: LoopSummary = { name: 'review-loop', description: 'Review and fix changes', agent_count: 1, triggers: [], valid: true, error_summary: null };
export const loopDetail: LoopDetail = { name: 'review-loop', description: 'Review and fix changes', valid: true, error_summary: null, triggers: [], resources: [], environment: null, files: [{ path: 'loop.md', media_type: 'text/markdown', size: 90, previewable: true }, { path: 'workflow.py', media_type: 'text/x-python', size: 120, previewable: true }, { path: 'binary.bin', media_type: null, size: 12, previewable: false }], agents: [{ name: 'reviewer', description: 'Reviews changes', path: 'agents/reviewer.md' }], runs: [runs[1]] };
export const backends: Backend[] = [{ name: 'codex', status: 'available', reason: null, cli_path: '/usr/bin/codex', version: '1.0.0', transport: 'cli', capabilities: { native_goal: true, structured_output: true, native_skills: false }, diagnosed_at: null }, { name: 'kimi', status: 'missing', reason: 'cli_not_found', cli_path: null, version: null, transport: 'cli', capabilities: { native_goal: false }, diagnosed_at: null }];
