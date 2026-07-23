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
  intervention?: Record<string, unknown>;
  responseStatus?: number;
  responseBody?: unknown;
};

function installFetch(config: FetchOptions = true) {
  vi.stubGlobal('EventSource', EventSourceMock);
  const durable = typeof config === 'boolean' ? config : config.durable ?? true;
  const waitingIntervention = typeof config === 'boolean' || !config.intervention ? { request_id: 'approve-1', key: 'approve', prompt: 'Approve?', schema: { type: 'boolean' }, status: 'pending', resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T22:00:00Z', responded_at: null } : config.intervention;
  const responseStatus = typeof config === 'boolean' ? 200 : config.responseStatus ?? 200;
  const responseBody = typeof config === 'boolean' ? null : config.responseBody ?? null;
  const calls = [] as unknown as string[] & { bodies: unknown[] };
  calls.bodies = [];
  const emptyLoop = { ...loopDetail, name: 'empty-loop', description: 'No agent files', agents: [], files: loopDetail.files.filter((item) => item.path === 'loop.md' || item.path === 'workflow.py') };
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, options?: RequestInit) => {
    const path = String(input);
    calls.push(`${options?.method ?? 'GET'} ${path}`);
    if (path.startsWith('/api/v1/runs?')) return response({ items: runs.filter((run) => path.includes('status=failed') ? run.status === 'failed' : true), next_cursor: null });
    if (path === '/api/v1/runs') return options?.method === 'POST' ? response(runs[0], 201) : response({ items: runs, next_cursor: null });
    if (path === '/api/v1/runs/run-live') return response(detail);
    if (path === '/api/v1/runs/run-waiting') return response({ ...detail, ...runs[1], allowed_actions: ['respond', 'stop'] });
    if (path === '/api/v1/runs/run-waiting/interventions') return response({ items: [waitingIntervention] });
    if (path === '/api/v1/runs/run-failed') return response({ ...detail, ...runs[2], allowed_actions: ['recover_retry', ...(durable ? ['recover_continue'] : []), 'rerun', 'reconcile'] });
    if (path === '/api/v1/runs/run-cancelled') return response({ ...detail, ...runs[3], allowed_actions: ['recover_retry', 'respond', 'rerun'] });
    if (path === '/api/v1/runs/run-cancelled/interventions') return response({ items: [{ request_id: 'approve-2', key: 'approve', prompt: 'Approve after cancel?', schema: { type: 'boolean' }, status: 'pending', resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T20:00:00Z', responded_at: null }] });
    if (path.includes(`/api/v1/runs/run-waiting/interventions/${waitingIntervention.request_id}/response`)) {
      calls.bodies.push(JSON.parse(String(options?.body)).response);
      return response(responseBody ?? { ...runs[1], status: 'running', allowed_actions: ['stop'] }, responseStatus);
    }
    if (path.includes('/api/v1/runs/run-cancelled/interventions/approve-2/response')) return response({ ...runs[3], status: 'running', allowed_actions: ['stop'] });
    if (path.includes('/api/v1/runs/run-live/')) return response({ ...runs[0], status: 'cancelled', allowed_actions: ['rerun'] });
    if (path === '/api/v1/loops') return response({ items: [loopSummary, { ...loopSummary, name: 'empty-loop', description: 'No agent files', agent_count: 0 }], next_cursor: null });
    if (path === '/api/v1/loops/review-loop') return response(loopDetail);
    if (path === '/api/v1/loops/empty-loop') return response(emptyLoop);
    if (path.includes('/api/v1/loops/review-loop/file')) return response({ content: path.includes('workflow.py') ? 'def run():\n    pass' : '# Review Loop\n\nOperational workflow.', media_type: 'text/plain', size: 40 });
    if (path.includes('/api/v1/loops/empty-loop/file')) return response({ content: '# Empty Loop', media_type: 'text/plain', size: 12 });
    if (path === '/api/v1/backends') return response({ items: backends });
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
  vi.unstubAllGlobals();
});

it('operates the Runs master-detail workspace and stream', async () => {
  const calls = installFetch();
  render(<App />);

  expect(await screen.findByText('run-live')).toBeVisible();
  expect(await screen.findByText('Phase graph')).toBeVisible();
  expect(screen.getAllByText('wf-review-a').length).toBe(2);
  expect(screen.getByText('1 malformed')).toBeVisible();
  fireEvent.click(screen.getByRole('tab', { name: 'Unattributed 1' }));
  expect(screen.getByText(/legacy/)).toBeVisible();
  fireEvent.click(screen.getByRole('tab', { name: 'Malformed 1' }));
  expect(screen.getByRole('heading', { name: 'Malformed events' })).toBeVisible();
  fireEvent.click(screen.getByRole('tab', { name: /^Events/ }));
  expect(screen.getAllByText('workflow output').length).toBeGreaterThan(0);
  expect(screen.queryByText(/"content":/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('wf-review-b'));
  expect(screen.getByText('wf-review-b', { selector: 'h2' })).toBeVisible();
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
  expect(screen.getByRole('button', { name: 'Continue failed session' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Retry failed call' }));
  await waitFor(() => expect(calls).toContain('POST /api/v1/runs/run-failed/recover'));
  fireEvent.click(screen.getByRole('button', { name: 'Rerun run' }));
  fireEvent.click(screen.getByRole('button', { name: 'Reconcile run' }));
  fireEvent.click(screen.getByText('Plan', { selector: '.phase-node span' }));
  fireEvent.click(screen.getByRole('button', { name: /wf-plan/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Open process inspector' }));
  fireEvent.click(screen.getByRole('button', { name: 'Close process inspector' }));
  fireEvent.click(screen.getByRole('button', { name: 'Back to Runs' }));

  fireEvent.click(screen.getByRole('button', { name: /New/ }));
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

  expect(await screen.findByRole('heading', { name: 'Approve?' })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Resume run' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Approve' }));

  await waitFor(() => expect(calls).toContain('POST /api/v1/runs/run-waiting/interventions/approve-1/response'));
  expect(calls.bodies).toContain(true);
});

it('answers string and number interventions with typed controls', async () => {
  const stringCalls = installFetch({ intervention: { request_id: 'name-1', key: 'name', prompt: 'Reviewer name?', schema: { type: 'string' }, status: 'pending', resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T22:00:00Z', responded_at: null } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByText('run-waiting'));
  fireEvent.change(await screen.findByRole('textbox', { name: 'Intervention response' }), { target: { value: 'Ada' } });
  fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
  await waitFor(() => expect(stringCalls.bodies).toContain('Ada'));
  cleanup();
  window.history.replaceState(null, '', '/');
  EventSourceMock.instances = [];
  vi.unstubAllGlobals();

  const numberCalls = installFetch({ intervention: { request_id: 'score-1', key: 'score', prompt: 'Risk score?', schema: { type: 'number' }, status: 'pending', resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T22:00:00Z', responded_at: null } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByText('run-waiting'));
  fireEvent.change(await screen.findByRole('spinbutton', { name: 'Intervention response' }), { target: { value: '4.5' } });
  fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
  await waitFor(() => expect(numberCalls.bodies).toContain(4.5));
});

it('answers JSON interventions and surfaces response errors', async () => {
  const objectCalls = installFetch({ intervention: { request_id: 'payload-1', key: 'payload', prompt: 'Structured payload?', schema: { type: 'object' }, status: 'pending', resume_mode: 'continue', call_id: '0002', can_continue_session: true, created_at: '2026-07-18T22:00:00Z', responded_at: null } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByText('run-waiting'));
  expect(await screen.findByText('Session continuation')).toBeVisible();
  fireEvent.change(await screen.findByRole('textbox', { name: 'Intervention response' }), { target: { value: '{"risk":"low"}' } });
  fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
  await waitFor(() => expect(objectCalls.bodies).toContainEqual({ risk: 'low' }));
  cleanup();
  window.history.replaceState(null, '', '/');
  EventSourceMock.instances = [];
  vi.unstubAllGlobals();

  const errorCalls = installFetch({ intervention: { request_id: 'free-1', key: 'free', prompt: 'Any value?', schema: null, status: 'pending', resume_mode: 'replay', call_id: null, can_continue_session: false, created_at: '2026-07-18T22:00:00Z', responded_at: null }, responseStatus: 422, responseBody: { error: { code: 'validation_failed', message: 'response must be object', details: {} } } });
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByText('run-waiting'));
  fireEvent.click(await screen.findByRole('button', { name: 'Submit' }));
  await waitFor(() => expect(errorCalls.bodies).toContain(null));
  expect(await screen.findByRole('alert')).toHaveTextContent('response must be object');
});

it('answers a cancelled pending intervention and keeps recovery controls', async () => {
  const calls = installFetch();
  render(<App />);
  await screen.findByRole('heading', { name: 'run-live' });
  fireEvent.click(screen.getByText('run-cancelled'));

  expect(await screen.findByRole('button', { name: 'Retry cancelled call' })).toBeVisible();
  expect(await screen.findByRole('heading', { name: 'Approve after cancel?' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Approve' }));

  await waitFor(() => expect(calls).toContain('POST /api/v1/runs/run-cancelled/interventions/approve-2/response'));
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
