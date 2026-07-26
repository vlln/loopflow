import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import App from './App';
import { backends, detail, loopDetail, loopSummary, runs } from './test/fixtures';

class EventSourceMock {
  static instances: EventSourceMock[] = [];
  listeners: Record<string, ((event: MessageEvent) => void)[]> = {};
  onerror: (() => void) | null = null;
  constructor(public url: string) { EventSourceMock.instances.push(this); }
  addEventListener(type: string, callback: EventListener) { (this.listeners[type] ??= []).push(callback as (event: MessageEvent) => void); }
  emit(type: string, data = '{}') { this.listeners[type]?.forEach((callback) => callback(new MessageEvent(type, { data }))); }
  close() {}
}

function response(body: unknown, status = 200) {
  return Promise.resolve({ ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) } as Response);
}

type FetchOptions = boolean | {
  durable?: boolean;
  intervention?: Record<string, unknown> | Record<string, unknown>[];
  responseStatus?: number;
  responseBody?: unknown;
  fileChanges?: Record<string, { seq: number; phase: string; phase_id: string; ts: string; changes: { path: string; action: string; size?: number; prev_size?: number }[] }[]>;
  runFile?: { status?: number; body?: unknown };
  pickDirectory?: { status?: number; body?: unknown };
  systemMeta?: { status?: number; body?: unknown };
  declaredArgs?: { name: string; default?: unknown; description?: string; required?: boolean }[];
  detailOverride?: Record<string, unknown>;
  pausedLoop?: boolean;
};

function installFetch(config: FetchOptions = true) {
  vi.stubGlobal('EventSource', EventSourceMock);
  const durable = typeof config === 'boolean' ? config : config.durable ?? true;
  const waitingInterventions = typeof config === 'boolean' || !config.intervention ? [{ request_id: 'approve-1', key: 'approve', prompt: 'Approve?', schema: { type: 'boolean' }, status: 'pending', resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T22:00:00Z', responded_at: null }] : Array.isArray(config.intervention) ? config.intervention : [config.intervention];
  const waitingIntervention = waitingInterventions[0];
  const responseStatus = typeof config === 'boolean' ? 200 : config.responseStatus ?? 200;
  const responseBody = typeof config === 'boolean' ? null : config.responseBody ?? null;
  const fileChangesMap = typeof config === 'boolean' ? {} : config.fileChanges ?? {};
  const runFileStatus = typeof config === 'boolean' ? 200 : config.runFile?.status ?? 200;
  const runFileBody = typeof config === 'boolean' ? null : config.runFile?.body ?? null;
  const pickStatus = typeof config === 'boolean' ? 200 : config.pickDirectory?.status ?? 200;
  const pickBody = typeof config === 'boolean' ? null : config.pickDirectory?.body ?? null;
  const metaStatus = typeof config === 'boolean' ? 200 : config.systemMeta?.status ?? 200;
  const metaBody = typeof config === 'boolean' ? null : config.systemMeta?.body ?? null;
  const declaredArgs = typeof config === 'boolean' ? undefined : config.declaredArgs;
  const detailOverride = typeof config === 'boolean' ? null : config.detailOverride ?? null;
  const pausedLoop = typeof config === 'boolean' ? false : config.pausedLoop ?? false;
  const pausedFields = pausedLoop ? { paused: true, paused_reason: 'failure_streak:5', consecutive_failures: 5 } : {};
  const declaredLoop = declaredArgs ? { ...loopSummary, declared_args: declaredArgs } : { ...loopSummary, ...pausedFields };
  const calls = [] as unknown as string[] & { bodies: unknown[] };
  calls.bodies = [];
  const emptyLoop = { ...loopDetail, name: 'empty-loop', description: 'No agent files', agents: [], files: loopDetail.files.filter((item) => item.path === 'loop.md' || item.path === 'workflow.py') };
  let loopUnpaused = false;
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, options?: RequestInit) => {
    const path = String(input);
    calls.push(`${options?.method ?? 'GET'} ${path}`);
    if (path.startsWith('/api/v1/runs?')) return response({ items: runs.filter((run) => path.includes('status=failed') ? run.status === 'failed' : true), next_cursor: null });
    if (path === '/api/v1/runs') {
      if (options?.method === 'POST') { calls.bodies.push(JSON.parse(String(options.body))); return response(runs[0], 201); }
      return response({ items: runs, next_cursor: null });
    }
    if (path === '/api/v1/runs/run-live') return response(detailOverride ? { ...detail, ...detailOverride } : detail);
    if (path === '/api/v1/runs/run-waiting') return response({ ...detail, ...runs[1], allowed_actions: ['respond', 'stop'], interventions: waitingInterventions });
    if (path === '/api/v1/runs/run-waiting/interventions') return response({ items: waitingInterventions });
    if (path === '/api/v1/runs/run-failed') return response({ ...detail, ...runs[2], allowed_actions: ['recover_retry', ...(durable ? ['recover_continue'] : []), 'rerun', 'reconcile'] });
    if (path === '/api/v1/runs/run-cancelled') return response({ ...detail, ...runs[3], allowed_actions: ['recover_retry', 'respond', 'rerun'] });
    if (path === '/api/v1/runs/run-stale') return response({ ...detail, ...runs.find((run) => run.run_id === 'run-stale'), allowed_actions: ['reconcile'] });
    if (path === '/api/v1/runs/run-cancelled/interventions') return response({ items: [{ request_id: 'approve-2', key: 'approve', prompt: 'Approve after cancel?', schema: { type: 'boolean' }, status: 'pending', resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T20:00:00Z', responded_at: null }] });
    if (path === '/api/v1/runs/run-waiting/interventions/responses') {
      calls.bodies.push(JSON.parse(String(options?.body)).responses);
      return response(responseBody ?? { ...runs[1], status: 'running', allowed_actions: ['stop'] }, responseStatus);
    }
    if (path === '/api/v1/runs/run-cancelled/interventions/responses') {
      calls.bodies.push(JSON.parse(String(options?.body)).responses);
      return response({ ...runs[3], status: 'running', allowed_actions: ['stop'] });
    }
    if (path.includes('/file-changes')) {
      const runId = path.match(/\/runs\/([^/]+)\/file-changes/)?.[1] ?? '';
      const items = fileChangesMap[runId] ?? [];
      return response({ items, count: items.length });
    }
    if (path.match(/\/api\/v1\/runs\/[^/]+\/file\?path=/)) {
      return response(runFileBody ?? { path: 'data/raw.json', media_type: 'application/json', content: '{"ok": true}', size: 12, read_only: true }, runFileStatus);
    }
    if (path.includes('/api/v1/runs/run-live/')) return response({ ...runs[0], status: 'cancelled', allowed_actions: ['rerun'] });
    if (path === '/api/v1/loops') return response({ items: [{ ...declaredLoop, ...(loopUnpaused ? { paused: false, paused_reason: null, consecutive_failures: 0 } : {}) }, { ...loopSummary, name: 'empty-loop', description: 'No agent files', agent_count: 0 }], next_cursor: null });
    if (path === '/api/v1/loops/review-loop') return response(declaredArgs ? { ...loopDetail, declared_args: declaredArgs } : { ...loopDetail, ...pausedFields });
    if (path === '/api/v1/loops/review-loop/unpause') { loopUnpaused = true; return response({ ...loopDetail, paused: false, paused_reason: null, consecutive_failures: 0 }); }
    if (path === '/api/v1/loops/empty-loop') return response(emptyLoop);
    if (path.includes('/api/v1/loops/review-loop/file')) return response({ content: path.includes('workflow.py') ? 'def run():\n    pass' : '# Review Loop\n\nOperational workflow.', media_type: 'text/plain', size: 40 });
    if (path.includes('/api/v1/loops/empty-loop/file')) return response({ content: '# Empty Loop', media_type: 'text/plain', size: 12 });
    if (path === '/api/v1/backends') return response({ items: backends });
    if (path === '/api/v1/system/pick-directory') return response(pickBody ?? { path: '/tmp/lf-picked', cancelled: false }, pickStatus);
    if (path === '/api/v1/system/meta') return response(metaBody ?? { version: '0.19.1' }, metaStatus);
    if (path.includes('/diagnostics')) return response({ name: 'codex', status: 'available', reason: null, exit_code: 0, stdout: 'codex 1.0.0', stderr: '', diagnosed_at: '2026-07-18T22:00:00Z' });
    return response({ error: { code: 'not_found', message: 'missing', details: {} } }, 404);
  }));
  return calls;
}

beforeEach(() => {
  EventSourceMock.instances = [];
  vi.stubGlobal('EventSource', EventSourceMock);
});

afterEach(() => {
  cleanup();
  window.history.replaceState(null, '', '/');
  localStorage.removeItem('lf-theme');
  delete document.documentElement.dataset.theme;
  vi.unstubAllGlobals();
});

it('operates the Runs master-detail workspace and stream', async () => {
  const calls = installFetch();
  render(<App />);

  expect(await screen.findByText('run-live')).toBeVisible();
  expect(await screen.findByText('Phase graph')).toBeVisible();
  expect(screen.getAllByText('call-a').length).toBe(1);
  expect(screen.getByText('1 malformed')).toBeVisible();
  fireEvent.click(screen.getByRole('tab', { name: 'Unattributed 1' }));
  expect(screen.getByText(/legacy/)).toBeVisible();
  fireEvent.click(screen.getByRole('tab', { name: 'Malformed 1' }));
  expect(screen.getByRole('heading', { name: 'Malformed events' })).toBeVisible();
  fireEvent.click(screen.getByRole('tab', { name: /^Events/ }));
  expect(screen.getAllByText('workflow output').length).toBeGreaterThan(0);
  expect(screen.queryByText(/"content":/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('call-b'));
  expect(screen.getByText(/Default · exit 0/)).toBeVisible();
  expect(EventSourceMock.instances[0].url).toContain('last_event_id=3');
  act(() => {
    EventSourceMock.instances[0].emit('run_event', JSON.stringify({ version: 2, event_id: 3, type: 'message', phase_id: 'review-2', call_id: 'call-a', payload: { text: 'next' } }));
  });
  fireEvent.click(screen.getByRole('button', { name: 'Stop run' }));
  await waitFor(() => expect(calls).toContain('POST /api/v1/runs/run-live/stop'));
  fireEvent.change(screen.getByLabelText('Filter status'), { target: { value: 'failed' } });
  await waitFor(() => expect(calls.some((call) => call.includes('status=failed'))).toBe(true));
});

it('creates a Run from the modal', async () => {
  installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  expect(await screen.findByRole('dialog', { name: 'New Run' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Start Run' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
});

it('operates secondary Run controls and handles invalid arguments', async () => {
  const calls = installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.change(screen.getByLabelText('Filter status'), { target: { value: 'failed' } });
  await waitFor(() => expect(calls.some((call) => call.includes('status=failed'))).toBe(true));
  fireEvent.click(screen.getByRole('listitem'));
  expect(await screen.findByRole('button', { name: 'Retry failed call' })).toBeVisible();
  expect(screen.getByRole('button', { name: 'Retry failed call' })).toHaveClass('primary-button');
  expect(screen.getByRole('button', { name: 'Continue failed session' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Retry failed call' }));
  await waitFor(() => expect(calls).toContain('POST /api/v1/runs/run-failed/recover'));
  fireEvent.click(screen.getByRole('button', { name: 'Rerun run' }));
  fireEvent.click(screen.getByRole('button', { name: 'Reconcile run' }));
  fireEvent.click(screen.getByText('Plan', { selector: '.phase-node span' }));
  fireEvent.click(screen.getByRole('button', { name: /call-plan/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Open file changes panel' }));
  fireEvent.click(screen.getByRole('button', { name: 'Close file changes panel' }));
  fireEvent.click(screen.getByRole('button', { name: 'Back to Runs' }));

  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  fireEvent.click(await screen.findByRole('button', { name: 'JSON' }));
  const argumentsInput = await screen.findByRole('textbox', { name: 'Arguments' });
  fireEvent.change(argumentsInput, { target: { value: '{invalid' } });
  fireEvent.click(screen.getByRole('button', { name: 'Start Run' }));
  expect(await screen.findByText(/Unexpected token|JSON/)).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
});

it('disables Continue when the failed backend has no durable session', async () => {
  installFetch(false);
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.change(screen.getByLabelText('Filter status'), { target: { value: 'failed' } });
  fireEvent.click(await screen.findByRole('listitem'));

  expect(await screen.findByRole('button', { name: 'Retry failed call' })).toBeEnabled();
  const unavailable = screen.getByRole('button', { name: 'Continue failed session unavailable' });
  expect(unavailable).toBeDisabled();
  expect(unavailable).toHaveAttribute('title', 'Backend did not persist a durable session or this cancel boundary is atomic');
  expect(screen.queryByRole('button', { name: 'Resume run' })).not.toBeInTheDocument();
});

it('answers a waiting intervention with a boolean control', async () => {
  const calls = installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByText('run-waiting'));

  expect(await screen.findByRole('heading', { name: '1 pending request' })).toBeVisible();
  expect(screen.getByText('Approve?')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Resume run' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'true' }));
  fireEvent.click(screen.getByRole('button', { name: 'Submit all' }));

  await waitFor(() => expect(calls).toContain('POST /api/v1/runs/run-waiting/interventions/responses'));
  expect(calls.bodies).toContainEqual([{ request_id: 'approve-1', response: 'true' }]);
});

it('answers string interventions with typed controls', async () => {
  const stringCalls = installFetch({ intervention: { request_id: 'name-1', key: 'name', prompt: 'Reviewer name?', schema: { type: 'string' }, status: 'pending', resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T22:00:00Z', responded_at: null } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByText('run-waiting'));
  fireEvent.change(await screen.findByRole('textbox', { name: 'Response for name' }), { target: { value: 'Ada' } });
  fireEvent.click(screen.getByRole('button', { name: 'Submit all' }));
  await waitFor(() => expect(stringCalls.bodies).toContainEqual([{ request_id: 'name-1', response: 'Ada' }]));
});

it('answers option interventions and surfaces response errors', async () => {
  const objectCalls = installFetch({ intervention: { request_id: 'payload-1', key: 'payload', prompt: 'Structured payload?', source: 'agent', options: ['low', 'high'], allow_custom: false, status: 'pending', resume_mode: 'continue', call_id: '0002', can_continue_session: true, created_at: '2026-07-18T22:00:00Z', responded_at: null } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByText('run-waiting'));
  expect(await screen.findByText('Session continuation')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'low' }));
  fireEvent.click(screen.getByRole('button', { name: 'Submit all' }));
  await waitFor(() => expect(objectCalls.bodies).toContainEqual([{ request_id: 'payload-1', response: 'low' }]));
  cleanup();
  window.history.replaceState(null, '', '/');
  EventSourceMock.instances = [];
  vi.unstubAllGlobals();

  const errorCalls = installFetch({ intervention: { request_id: 'free-1', key: 'free', prompt: 'Any value?', schema: null, status: 'pending', resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T22:00:00Z', responded_at: null }, responseStatus: 422, responseBody: { error: { code: 'validation_failed', message: 'response must be string', details: {} } } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByText('run-waiting'));
  fireEvent.change(await screen.findByRole('textbox', { name: 'Response for free' }), { target: { value: 'anything' } });
  fireEvent.click(await screen.findByRole('button', { name: 'Submit all' }));
  await waitFor(() => expect(errorCalls.bodies).toContainEqual([{ request_id: 'free-1', response: 'anything' }]));
  expect(await screen.findByRole('alert')).toHaveTextContent('response must be string');
  expect(screen.getByRole('status')).toHaveTextContent('response must be string');
});

it('answers a cancelled pending intervention and keeps recovery controls', async () => {
  const calls = installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByText('run-cancelled'));

  expect(await screen.findByRole('button', { name: 'Retry cancelled call' })).toHaveClass('secondary-button');
  expect(await screen.findByText('Approve after cancel?')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'true' }));
  fireEvent.click(screen.getByRole('button', { name: 'Submit all' }));

  await waitFor(() => expect(calls).toContain('POST /api/v1/runs/run-cancelled/interventions/responses'));
});

it('shows answered interventions as read-only history', async () => {
  installFetch({ intervention: { request_id: 'approve-answered', key: 'approve', prompt: 'Approved already?', schema: { type: 'boolean' }, status: 'answered', response: true, resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T22:00:00Z', responded_at: '2026-07-18T22:01:00Z' } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByText('run-waiting'));

  expect(await screen.findByText('Requests')).toBeVisible();
  fireEvent.click(screen.getByText('Requests'));
  expect(screen.getByText('Approved already?')).toBeVisible();
  expect(screen.getByText('true')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'true' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Submit all' })).not.toBeInTheDocument();
});

it('answers multiple pending requests in one submit', async () => {
  installFetch({ intervention: [
    { request_id: 'first', key: 'first', prompt: 'First pending?', schema: { type: 'boolean' }, status: 'pending', resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T22:00:00Z', responded_at: null },
    { request_id: 'second', key: 'second', prompt: 'Second pending?', options: ['ship'], allow_custom: true, status: 'pending', resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T22:01:00Z', responded_at: null },
    { request_id: 'done', key: 'done', prompt: 'Done request?', schema: { type: 'boolean' }, status: 'answered', response: false, resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T22:02:00Z', responded_at: '2026-07-18T22:03:00Z' },
  ] });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByText('run-waiting'));

  expect(await screen.findByRole('heading', { name: '2 pending requests' })).toBeVisible();
  expect(screen.getByText('First pending?')).toBeVisible();
  expect(screen.getByText('Second pending?')).toBeVisible();
  fireEvent.click(screen.getByText('Requests'));
  expect(screen.getByText('Done request?')).toBeVisible();
});

it('navigates Loop declarations and renders files', async () => {
  const calls = installFetch();
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Loops' }));
  expect(await screen.findByText('Review and fix changes')).toBeVisible();
  expect(await screen.findByRole('heading', { name: 'Review Loop' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Workflow' }));
  expect(await screen.findByText(/def run/)).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: /Agents/ }));
  expect(await screen.findByRole('button', { name: /reviewer/ })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: /empty-loop/ }));
  expect(await screen.findByRole('heading', { name: 'empty-loop' })).toBeVisible();
  expect(calls.some((call) => call.includes('/empty-loop/file') && call.includes('agents/'))).toBe(false);
});

it('scans Backends and runs diagnostics', async () => {
  const calls = installFetch();
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Backends' }));
  expect((await screen.findAllByText('/usr/bin/codex')).length).toBe(2);
  expect(screen.getAllByText('Unknown').length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole('button', { name: /Run check/ }));
  expect(await screen.findByText('codex 1.0.0')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: /kimi/ }));
  fireEvent.click(screen.getByRole('button', { name: /Scan/ }));
  await waitFor(() => expect(calls.filter((call) => call === 'GET /api/v1/backends')).toHaveLength(2));
});

it('shows API failures without replacing the workspace', async () => {
  vi.stubGlobal('fetch', vi.fn(() => response({ error: { code: 'internal_error', message: 'fixture failed', details: {} } }, 500)));
  render(<App />);
  expect(await screen.findByRole('alert')).toHaveTextContent('fixture failed');
  expect(screen.getByRole('heading', { name: 'Runs' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss error' }));
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

// --- AC-024: File change observation WebUI rendering ---

const fileChangeRecords = [
  { seq: 1, phase: 'Plan', phase_id: 'plan-1', ts: '2026-07-18T22:00:01Z', changes: [{ path: 'data/raw.json', action: 'created', size: 1024 }] },
  { seq: 2, phase: 'Review', phase_id: 'review-2', ts: '2026-07-18T22:00:03Z', changes: [
    { path: 'data/raw.json', action: 'modified', size: 2048, prev_size: 1024 },
    { path: 'data/clean.json', action: 'created', size: 512 },
  ] },
];

it('AC-024-N-4: renders file changes tree with created action and size', async () => {
  installFetch({ fileChanges: { 'run-live': fileChangeRecords } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  const panel = await screen.findByTestId('file-changes-panel');
  expect(panel).toBeVisible();
  expect(screen.getAllByText('raw.json').length).toBeGreaterThan(0);
  expect(screen.getAllByText('created').length).toBeGreaterThan(0);
  expect(screen.getAllByText(/1024/).length).toBeGreaterThan(0);
});

it('AC-024-N-5: tree merges changes from all phases with latest action and size', async () => {
  installFetch({ fileChanges: { 'run-live': fileChangeRecords } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  await screen.findByTestId('file-changes-panel');
  expect(screen.getByText('data')).toBeVisible();
  expect(screen.getByText('raw.json')).toBeVisible();
  expect(screen.getByText('modified')).toBeVisible();
  expect(screen.getByText(/2048/)).toBeVisible();
  expect(screen.getByText('clean.json')).toBeVisible();
});

it('AC-024-B-6: legacy run without file_changes shows empty state, no error', async () => {
  installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  const panel = await screen.findByTestId('file-changes-panel');
  expect(panel).toBeVisible();
  expect(screen.getByText('No file changes observed')).toBeVisible();
});

it('AC-024-B-7: run with no changes shows empty state', async () => {
  installFetch({ fileChanges: { 'run-live': [] } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  const panel = await screen.findByTestId('file-changes-panel');
  expect(panel).toBeVisible();
  expect(screen.getByText('No file changes observed')).toBeVisible();
});

it('AC-024-N-7: SSE file_changes push appends to tree in real-time', async () => {
  installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  await screen.findByText('No file changes observed');
  act(() => {
    EventSourceMock.instances[0].emit('file_changes', JSON.stringify({
      seq: 1, phase: 'Review', phase_id: 'review-2', ts: '2026-07-18T22:00:05Z',
      changes: [{ path: 'output/result.json', action: 'created', size: 256 }],
    }));
  });
  await waitFor(() => expect(screen.getByText('result.json')).toBeVisible());
  expect(screen.getByText('output')).toBeVisible();
  expect(screen.getByText('created')).toBeVisible();
});

it('AC-024-N-8: tree markers follow the selected phase', async () => {
  installFetch({ fileChanges: { 'run-live': fileChangeRecords } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  await screen.findByTestId('file-changes-panel');
  expect(screen.getByText('1024 → 2048 B')).toBeVisible();
  fireEvent.click(screen.getByText('Plan', { selector: '.phase-node span' }));
  expect(screen.getByText('1024 B')).toBeVisible();
  expect(screen.queryByText('1024 → 2048 B')).not.toBeInTheDocument();
});

// --- AC-025: Run working directory + file preview ---

it('AC-025-N-3: New Run submits working_directory only when filled', async () => {
  const calls = installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  fireEvent.change(await screen.findByRole('textbox', { name: 'Working directory' }), { target: { value: '/tmp/lf-work' } });
  fireEvent.click(screen.getByRole('button', { name: 'Start Run' }));
  await waitFor(() => expect(calls.bodies).toContainEqual(expect.objectContaining({ working_directory: '/tmp/lf-work' })));

  cleanup();
  window.history.replaceState(null, '', '/');
  EventSourceMock.instances = [];
  vi.unstubAllGlobals();

  const blankCalls = installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  await screen.findByRole('dialog', { name: 'New Run' });
  fireEvent.click(screen.getByRole('button', { name: 'Start Run' }));
  await waitFor(() => expect(blankCalls.bodies.length).toBe(1));
  expect(blankCalls.bodies[0]).not.toHaveProperty('working_directory');
});

it('AC-025-N-5: clicking a file in the tree previews its content read-only', async () => {
  installFetch({ fileChanges: { 'run-live': fileChangeRecords }, runFile: { body: { path: 'data/raw.json', media_type: 'application/json', content: '{"ok": true}', size: 12, read_only: true } } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  await screen.findByTestId('file-changes-panel');
  fireEvent.click(screen.getByRole('button', { name: 'Preview data/raw.json' }));
  expect(await screen.findByRole('dialog', { name: 'raw.json' })).toBeVisible();
  expect(await screen.findByText('{"ok": true}')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Close preview' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

it('AC-025-E-3: previewing a deleted file shows a friendly not-found message', async () => {
  installFetch({
    fileChanges: { 'run-live': [{ seq: 1, phase: 'Review', phase_id: 'review-2', ts: '2026-07-18T22:00:03Z', changes: [{ path: 'tmp/scratch.txt', action: 'deleted', prev_size: 10 }] }] },
    runFile: { status: 404, body: { error: { code: 'file_not_found', message: 'file not found', details: {} } } },
  });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  await screen.findByTestId('file-changes-panel');
  fireEvent.click(screen.getByRole('button', { name: 'Preview tmp/scratch.txt' }));
  expect(await screen.findByRole('dialog', { name: 'scratch.txt' })).toBeVisible();
  expect(await screen.findByRole('alert')).toHaveTextContent('File no longer exists');
});

// --- AC-025: native directory picker / AC-014: arguments editor ---

it('AC-025-N-6: Browse fills the working directory from the native picker', async () => {
  const calls = installFetch({ pickDirectory: { body: { path: '/tmp/lf-picked', cancelled: false } } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  fireEvent.click(await screen.findByRole('button', { name: /Browse/ }));
  const workdir = screen.getByRole('textbox', { name: 'Working directory' });
  await waitFor(() => expect(workdir).toHaveValue('/tmp/lf-picked'));
  fireEvent.click(screen.getByRole('button', { name: 'Start Run' }));
  await waitFor(() => expect(calls.bodies).toContainEqual(expect.objectContaining({ working_directory: '/tmp/lf-picked' })));
});

it('AC-025-B-6: cancelling the picker leaves the working directory unchanged', async () => {
  installFetch({ pickDirectory: { body: { path: null, cancelled: true } } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  const workdir = await screen.findByRole('textbox', { name: 'Working directory' });
  fireEvent.change(workdir, { target: { value: '/tmp/manual' } });
  fireEvent.click(screen.getByRole('button', { name: /Browse/ }));
  await waitFor(() => expect(screen.getByRole('button', { name: /Browse/ })).toBeEnabled());
  expect(workdir).toHaveValue('/tmp/manual');
});

it('AC-025-B-7: unsupported platform hides the Browse button', async () => {
  installFetch({ pickDirectory: { status: 501, body: { error: { code: 'not_supported', message: 'Directory picker is only supported on macOS', details: {} } } } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  fireEvent.click(await screen.findByRole('button', { name: /Browse/ }));
  await waitFor(() => expect(screen.queryByRole('button', { name: /Browse/ })).not.toBeInTheDocument());
  expect(screen.getByRole('textbox', { name: 'Working directory' })).toBeVisible();
});

it('AC-014-N-9: arguments editor builds a typed args object', async () => {
  const calls = installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  fireEvent.click(await screen.findByRole('button', { name: 'Add argument' }));
  fireEvent.click(screen.getByRole('button', { name: 'Add argument' }));
  const keys = screen.getAllByRole('textbox', { name: 'Argument key' });
  const values = screen.getAllByRole('textbox', { name: 'Argument value' });
  fireEvent.change(keys[0], { target: { value: 'name' } });
  fireEvent.change(values[0], { target: { value: 'review' } });
  fireEvent.change(keys[1], { target: { value: 'count' } });
  fireEvent.change(values[1], { target: { value: '2' } });
  fireEvent.change(keys[2], { target: { value: 'debug' } });
  fireEvent.change(values[2], { target: { value: 'true' } });
  fireEvent.click(screen.getByRole('button', { name: 'Start Run' }));
  await waitFor(() => expect(calls.bodies).toContainEqual(expect.objectContaining({ args: { name: 'review', count: 2, debug: true } })));
});

it('AC-014-B-3: blank-key rows are ignored and an empty editor submits {}', async () => {
  const calls = installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  fireEvent.click(await screen.findByRole('button', { name: 'Add argument' }));
  const keys = screen.getAllByRole('textbox', { name: 'Argument key' });
  const values = screen.getAllByRole('textbox', { name: 'Argument value' });
  fireEvent.change(values[0], { target: { value: 'orphan' } });
  fireEvent.change(keys[1], { target: { value: 'mode' } });
  fireEvent.change(values[1], { target: { value: 'fast' } });
  fireEvent.click(screen.getByRole('button', { name: 'Start Run' }));
  await waitFor(() => expect(calls.bodies).toContainEqual(expect.objectContaining({ args: { mode: 'fast' } })));

  cleanup();
  window.history.replaceState(null, '', '/');
  EventSourceMock.instances = [];
  vi.unstubAllGlobals();

  const blankCalls = installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  await screen.findByRole('dialog', { name: 'New Run' });
  fireEvent.click(screen.getByRole('button', { name: 'Start Run' }));
  await waitFor(() => expect(blankCalls.bodies).toContainEqual(expect.objectContaining({ args: {} })));
});

it('AC-014-B-4: invalid JSON in JSON mode shows an error and sends nothing', async () => {
  const calls = installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  fireEvent.click(await screen.findByRole('button', { name: 'JSON' }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Arguments' }), { target: { value: '{invalid' } });
  fireEvent.click(screen.getByRole('button', { name: 'Start Run' }));
  expect(await screen.findByText(/Unexpected token|JSON/)).toBeVisible();
  expect(calls.bodies).toHaveLength(0);
});

// --- AC-015: declared phases merge semantics (ADR-0040) ---

it('AC-015-N-7: executed declared phase replaces its placeholder, others stay pending', async () => {
  installFetch({
    detailOverride: {
      declared_phases: [{ title: '采集', detail: '' }, { title: '处理', detail: '' }],
      graph: {
        nodes: [{ phase: '采集', occurrence_count: 1, is_current: true }],
        edges: [],
        current_phase_id: 'caiji-1',
      },
      occurrences: [{ phase_id: 'caiji-1', phase: '采集', occurrence: 1, started_at: '2026-07-18T22:00:00Z', ended_at: null, call_ids: ['call-a'] }],
    },
  });
  render(<App />);

  const executed = (await screen.findByText('采集', { selector: '.phase-node span' })).closest('.phase-node')!;
  expect(executed.className).not.toContain('is-declared');
  expect(executed.className).toContain('is-current');
  expect(executed.textContent).toContain('×1');
  const pending = screen.getByText('处理', { selector: '.phase-node span' }).closest('.phase-node')!;
  expect(pending.className).toContain('is-declared');
  expect(pending.textContent).toContain('pending');
});

it('AC-015-N-8: undeclared runtime phase renders with the undeclared marker', async () => {
  installFetch({
    detailOverride: {
      declared_phases: [{ title: '采集', detail: '' }, { title: '处理', detail: '' }],
      graph: {
        nodes: [
          { phase: '采集', occurrence_count: 1, is_current: false },
          { phase: '归档', occurrence_count: 1, is_current: true },
        ],
        edges: [{ from: '采集', to: '归档', count: 1, is_backedge: false }],
        current_phase_id: 'guidang-1',
      },
      occurrences: [
        { phase_id: 'caiji-1', phase: '采集', occurrence: 1, started_at: '2026-07-18T22:00:00Z', ended_at: '2026-07-18T22:00:01Z', call_ids: ['call-a'] },
        { phase_id: 'guidang-1', phase: '归档', occurrence: 1, started_at: '2026-07-18T22:00:02Z', ended_at: null, call_ids: ['call-b'] },
      ],
    },
  });
  render(<App />);

  const undeclared = (await screen.findByText('归档', { selector: '.phase-node span' })).closest('.phase-node')!;
  expect(undeclared.className).toContain('is-undeclared');
  expect(undeclared.className).not.toContain('is-declared');
  const declared = screen.getByText('采集', { selector: '.phase-node span' }).closest('.phase-node')!;
  expect(declared.className).not.toContain('is-undeclared');
  expect(declared.className).not.toContain('is-declared');
  const pending = screen.getByText('处理', { selector: '.phase-node span' }).closest('.phase-node')!;
  expect(pending.className).toContain('is-declared');
});

// --- AC-014: rail version sync / declared arguments prefill / AC-019: theme toggle ---

it('AC-014-N-11: rail shows the version from system meta', async () => {
  installFetch();
  render(<App />);
  expect(await screen.findByText('v0.19.1')).toBeVisible();
});

it('AC-014-N-11: rail keeps a neutral placeholder when system meta fails', async () => {
  installFetch({ systemMeta: { status: 404, body: { error: { code: 'not_found', message: 'missing', details: {} } } } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  expect(screen.getByText('v—')).toBeVisible();
});

it('AC-014-N-10: declared args prefill the editor and empty rows are skipped on submit', async () => {
  const calls = installFetch({ declaredArgs: [{ name: 'review', default: 'main', required: true }, { name: 'count' }] });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  await screen.findByRole('dialog', { name: 'New Run' });
  await waitFor(() => expect(screen.getAllByRole('textbox', { name: 'Argument key' })).toHaveLength(2));
  const keys = screen.getAllByRole('textbox', { name: 'Argument key' });
  const values = screen.getAllByRole('textbox', { name: 'Argument value' });
  expect(keys[0]).toHaveValue('review');
  expect(values[0]).toHaveValue('main');
  expect(keys[1]).toHaveValue('count');
  expect(values[1]).toHaveValue('');
  expect(screen.getByTitle('Required')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Start Run' }));
  await waitFor(() => expect(calls.bodies).toContainEqual(expect.objectContaining({ args: { review: 'main' } })));
});

it('AC-014-N-10: switching loops resets the editor to that loop declarations', async () => {
  installFetch({ declaredArgs: [{ name: 'review', default: 'main', required: true }, { name: 'count' }] });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  await waitFor(() => expect(screen.getAllByRole('textbox', { name: 'Argument key' })).toHaveLength(2));
  expect(screen.getAllByRole('textbox', { name: 'Argument key' })[0]).toHaveValue('review');
  fireEvent.change(screen.getAllByRole('textbox', { name: 'Argument value' })[0], { target: { value: 'edited' } });
  fireEvent.change(screen.getByLabelText('Loop'), { target: { value: 'empty-loop' } });
  await waitFor(() => expect(screen.getAllByRole('textbox', { name: 'Argument key' })).toHaveLength(1));
  expect(screen.getByRole('textbox', { name: 'Argument key' })).toHaveValue('');
  fireEvent.change(screen.getByLabelText('Loop'), { target: { value: 'review-loop' } });
  await waitFor(() => expect(screen.getAllByRole('textbox', { name: 'Argument key' })).toHaveLength(2));
  expect(screen.getAllByRole('textbox', { name: 'Argument value' })[0]).toHaveValue('main');
});

it('AC-014-B-5: a loop without declared args starts with a blank editor', async () => {
  installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByRole('button', { name: /New/ }));
  await screen.findByRole('dialog', { name: 'New Run' });
  const keys = await screen.findAllByRole('textbox', { name: 'Argument key' });
  expect(keys).toHaveLength(1);
  expect(keys[0]).toHaveValue('');
  expect(screen.getByRole('textbox', { name: 'Argument value' })).toHaveValue('');
});

it('AC-019-N-5: theme toggle switches data-theme and persists across renders', async () => {
  installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  expect(document.documentElement.dataset.theme).toBe('dark');
  fireEvent.click(screen.getByRole('button', { name: 'Switch to light theme' }));
  expect(document.documentElement.dataset.theme).toBe('light');
  expect(localStorage.getItem('lf-theme')).toBe('light');
  cleanup();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  expect(document.documentElement.dataset.theme).toBe('light');
  fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
  expect(document.documentElement.dataset.theme).toBe('dark');
  expect(localStorage.getItem('lf-theme')).toBe('dark');
});


it('renders run error summary and failure category in list and detail', async () => {
  installFetch();
  render(<App />);
  expect(await screen.findByText('[quota] Agent failed')).toBeVisible();
  fireEvent.click(screen.getByText('run-failed'));
  const banner = await screen.findByRole('alert');
  expect(banner).toHaveTextContent('quota');
  expect(banner).toHaveTextContent('Agent failed');
});

it('renders stale grace period with remaining time in list and detail', async () => {
  installFetch();
  render(<App />);
  expect(await screen.findByText('Unreachable (grace period) · 23h 0m left')).toBeVisible();
  fireEvent.click(screen.getByText('run-stale'));
  expect(await screen.findByRole('heading', { name: 'run-stale' })).toBeVisible();
  expect(screen.getAllByText('Unreachable (grace period) · 23h 0m left').length).toBe(2);
  expect(screen.getByRole('button', { name: 'Reconcile run' })).toBeEnabled();
});

it('shows paused loop badge with streak and unpauses via API', async () => {
  const calls = installFetch({ pausedLoop: true });
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Loops' }));
  expect(await screen.findByText('failure_streak:5')).toBeVisible();
  expect(screen.getAllByText('paused').length).toBe(2);
  expect(screen.getAllByText(/streak ×5/).length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole('button', { name: 'Unpause loop' }));
  await waitFor(() => expect(calls).toContain('POST /api/v1/loops/review-loop/unpause'));
  await waitFor(() => expect(screen.queryByText('failure_streak:5')).not.toBeInTheDocument());
});
