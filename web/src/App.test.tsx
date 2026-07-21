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

function installFetch() {
  const calls: string[] = [];
  const emptyLoop = { ...loopDetail, name: 'empty-loop', description: 'No agent files', agents: [], files: loopDetail.files.filter((item) => item.path === 'loop.md' || item.path === 'workflow.py') };
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, options?: RequestInit) => {
    const path = String(input);
    calls.push(`${options?.method ?? 'GET'} ${path}`);
    if (path.startsWith('/api/v1/runs?')) return response({ items: runs.filter((run) => path.includes('status=failed') ? run.status === 'failed' : true), next_cursor: null });
    if (path === '/api/v1/runs') return options?.method === 'POST' ? response(runs[0], 201) : response({ items: runs, next_cursor: null });
    if (path === '/api/v1/runs/run-live') return response(detail);
    if (path === '/api/v1/runs/run-failed') return response({ ...detail, ...runs[1], allowed_actions: ['resume', 'rerun', 'reconcile'] });
    if (path.includes('/api/v1/runs/run-live/')) return response({ ...runs[0], status: 'stopped', allowed_actions: ['resume'] });
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
  expect(await screen.findByRole('button', { name: 'Resume run' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Resume run' }));
  await waitFor(() => expect(calls).toContain('POST /api/v1/runs/run-failed/resume'));
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
