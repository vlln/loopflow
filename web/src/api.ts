import type { Backend, Diagnostic, LoopDetail, LoopSummary, Page, RunDetail, RunEvent, RunSummary } from './types';

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number, public details: Record<string, unknown> = {}) {
    super(message);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers: options?.body ? { 'Content-Type': 'application/json', ...options.headers } : options?.headers,
  });
  const body = await response.json();
  if (!response.ok) {
    throw new ApiError(body.error?.code ?? 'internal_error', body.error?.message ?? 'Request failed', response.status, body.error?.details);
  }
  return body as T;
}

export const api = {
  runs: (params = '') => request<Page<RunSummary>>(`/runs${params}`),
  run: (id: string) => request<RunDetail>(`/runs/${encodeURIComponent(id)}`),
  createRun: (body: Record<string, unknown>) => request<RunSummary>('/runs', { method: 'POST', body: JSON.stringify(body) }),
  runAction: (id: string, action: string, body?: Record<string, unknown>) => request<RunSummary>(`/runs/${encodeURIComponent(id)}/${action}`, { method: 'POST', ...(body ? { body: JSON.stringify(body) } : {}) }),
  loops: () => request<Page<LoopSummary>>('/loops'),
  loop: (name: string) => request<LoopDetail>(`/loops/${encodeURIComponent(name)}`),
  loopFile: (name: string, path: string) => request<{ content: string; media_type: string; size: number }>(`/loops/${encodeURIComponent(name)}/file?path=${encodeURIComponent(path)}`),
  backends: () => request<{ items: Backend[] }>('/backends'),
  diagnose: (name: string) => request<Diagnostic>(`/backends/${encodeURIComponent(name)}/diagnostics`, { method: 'POST', body: JSON.stringify({ timeout_ms: 5000 }) }),
};

export function connectRunEvents(runId: string, lastEventId: number, onEvent: (event: RunEvent) => void, onState: (state: 'live' | 'closed' | 'error') => void): () => void {
  const source = new EventSource(`/api/v1/runs/${encodeURIComponent(runId)}/events?last_event_id=${lastEventId}`);
  source.addEventListener('open', () => onState('live'));
  source.addEventListener('run_event', (message) => onEvent(JSON.parse((message as MessageEvent).data)));
  source.addEventListener('stream_end', () => { onState('closed'); source.close(); });
  source.addEventListener('stream_error', () => { onState('error'); source.close(); });
  source.onerror = () => onState('error');
  return () => source.close();
}
