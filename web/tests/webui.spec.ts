import { expect, test, type Page } from '@playwright/test';

import { backends, detail, loopDetail, loopSummary, runs } from '../src/test/fixtures';

const longOutput = 'x'.repeat(500);

async function installApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

    if (path.endsWith('/events')) {
      return route.fulfill({
        contentType: 'text/event-stream',
        body: `event: run_event\ndata: ${JSON.stringify({ version: 2, event_id: 4, type: 'message', phase_id: 'review-2', call_id: 'call-a', payload: { text: longOutput } })}\n\nevent: stream_end\ndata: {"last_event_id":4}\n\n`,
      });
    }
    if (path === '/api/v1/runs' && request.method() === 'POST') return json(runs[0], 201);
    if (path === '/api/v1/runs') {
      const status = url.searchParams.get('status');
      const query = url.searchParams.get('q')?.toLowerCase();
      const items = runs.filter((run) => (!status || run.status === status) && (!query || `${run.run_id} ${run.loop}`.toLowerCase().includes(query)));
      return json({ items, next_cursor: null });
    }
    if (path === '/api/v1/runs/run-live') return json({ ...detail, events: [...detail.events, { version: 2, event_id: 4, type: 'message', phase_id: 'review-2', call_id: 'call-a', payload: { text: longOutput } }] });
    if (path === '/api/v1/runs/run-failed') return json({ ...detail, ...runs[1], allowed_actions: ['resume'] });
    if (/\/api\/v1\/runs\/[^/]+\/(stop|resume|rerun|reconcile)$/.test(path)) return json({ ...runs[0], status: 'stopped', allowed_actions: ['resume'] });
    if (path === '/api/v1/loops') return json({ items: [loopSummary], next_cursor: null });
    if (path === '/api/v1/loops/review-loop') return json(loopDetail);
    if (path === '/api/v1/loops/review-loop/file') return json({ content: url.searchParams.get('path') === 'workflow.py' ? 'def run():\n    return "review"' : '# Review Loop\n\nOperational workflow.', media_type: 'text/plain', size: 40 });
    if (path === '/api/v1/backends') return json({ items: backends });
    if (path === '/api/v1/backends/codex/diagnostics') return json({ name: 'codex', status: 'available', reason: null, exit_code: 0, stdout: 'codex 1.0.0', stderr: 'token=[REDACTED]', diagnosed_at: '2026-07-18T22:00:00Z' });
    return json({ error: { code: 'not_found', message: 'fixture missing', details: {} } }, 404);
  });
}

async function expectNoPageOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.width);
}

test.beforeEach(async ({ page }) => {
  await installApi(page);
  await page.emulateMedia({ reducedMotion: 'reduce', colorScheme: 'dark' });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Runs' })).toBeVisible();
});

test('operates Runs without overflow and renders a nonblank phase graph', async ({ page }, testInfo) => {
  const mobile = testInfo.project.name === 'chromium-390';
  const tablet = testInfo.project.name === 'chromium-1024';
  const liveRun = page.getByRole('listitem').filter({ hasText: 'lf_tmp-review-workspace' }).first();
  await expect(liveRun).toBeVisible();
  if (mobile) await liveRun.click();
  await expect(page.getByRole('heading', { name: 'Phase graph' })).toBeVisible();
  await expect(page.getByRole('tab', { name: /Unattributed/ })).toBeVisible();
  await page.getByRole('tab', { name: /Unattributed/ }).click();
  await expect(page.getByRole('heading', { name: 'Unattributed events' })).toBeVisible();
  await page.getByRole('tab', { name: /^Events/ }).click();
  await expect(page.getByText('workflow output').first()).toBeVisible();
  await expect(page.getByText(/"content":/)).toHaveCount(0);

  const flow = page.getByTestId('phase-flow');
  const nodes = flow.locator('.react-flow__node');
  await expect(nodes).toHaveCount(2);
  const flowBox = await flow.boundingBox();
  for (const node of await nodes.all()) {
    const box = await node.boundingBox();
    expect(box?.width).toBeGreaterThan(20);
    expect(box?.height).toBeGreaterThan(10);
    expect(box!.x).toBeGreaterThanOrEqual(flowBox!.x);
    expect(box!.y).toBeGreaterThanOrEqual(flowBox!.y);
    expect(box!.x + box!.width).toBeLessThanOrEqual(flowBox!.x + flowBox!.width);
    expect(box!.y + box!.height).toBeLessThanOrEqual(flowBox!.y + flowBox!.height);
    expect(await node.evaluate((element) => getComputedStyle(element.firstElementChild!).backgroundColor)).not.toBe('rgba(0, 0, 0, 0)');
  }
  expect((await flow.screenshot()).byteLength).toBeGreaterThan(1000);

  await page.getByRole('button', { name: 'Open process inspector' }).click();
  if (mobile || tablet) await expect(page.getByRole('button', { name: 'Close process inspector' })).toBeVisible();
  await expectNoPageOverflow(page);
  const log = page.locator('.process-log');
  await expect(log).toContainText(longOutput);
  expect(await log.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);

  if (mobile || tablet) await page.getByRole('button', { name: 'Close process inspector' }).click();
  if (!mobile) {
    await page.getByLabel('Filter status').selectOption('failed');
    const failedRun = page.getByRole('listitem').filter({ hasText: 'lf_tmp-review-workspace' }).first();
    await expect(failedRun).toBeVisible();
    await failedRun.click();
    await expect(page).toHaveURL(/run=run-failed/);
    await expect(page.getByRole('button', { name: 'Resume run' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Stop run' })).toHaveCount(0);
  }
  await page.screenshot({ path: testInfo.outputPath('runs.png'), fullPage: true });
});

test('navigates Loops and Backends responsively', async ({ page }, testInfo) => {
  await page.getByRole('button', { name: 'Loops' }).click();
  await expect(page.getByRole('heading', { name: 'Review Loop' })).toBeVisible();
  await page.getByRole('button', { name: 'Workflow' }).click();
  await expect(page.getByText(/def run/)).toBeVisible();
  await page.getByRole('button', { name: /Agents/ }).click();
  await expect(page.getByRole('button', { name: /reviewer/ })).toBeVisible();
  await expectNoPageOverflow(page);

  await page.getByRole('button', { name: 'Backends' }).click();
  await expect(page.getByRole('heading', { name: 'Backends' })).toBeVisible();
  await page.getByRole('button', { name: /Run check/ }).click();
  await expect(page.getByText('token=[REDACTED]')).toBeVisible();
  await expect(page.getByText(/lf-secret/)).toHaveCount(0);
  await expectNoPageOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('backends.png'), fullPage: true });
});

test('all icon-only controls expose names and tooltips', async ({ page }) => {
  const iconButtons = page.locator('button.icon-button');
  const count = await iconButtons.count();
  expect(count).toBeGreaterThan(0);
  for (let index = 0; index < count; index += 1) {
    const button = iconButtons.nth(index);
    expect(await button.getAttribute('aria-label')).toBeTruthy();
    expect(await button.getAttribute('title')).toBe(await button.getAttribute('aria-label'));
  }
});

test('keeps a thousand Runs reachable without resizing the workspace', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-1440', 'large-list boundary is viewport-independent');
  const bulkRuns = Array.from({ length: 1000 }, (_, index) => { const id = `bulk-${String(index + 1).padStart(4, '0')}`; return { ...runs[1], run_id: id, working_directory: `lf_tmp-bulk-${String(index + 1).padStart(4, '0')}` }; });
  await page.unroute('**/api/v1/**');
  await page.route('**/api/v1/runs?*', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: bulkRuns, next_cursor: null }) }));
  await page.route('**/api/v1/runs/*', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ...detail, ...bulkRuns.at(-1), allowed_actions: ['resume'] }) }));
  await page.getByLabel('Search runs').fill('bulk');
  const list = page.locator('.run-list');
  const width = await list.evaluate((element) => element.getBoundingClientRect().width);
  const last = page.getByRole('listitem').filter({ hasText: 'lf_tmp-bulk-1000' });
  await last.scrollIntoViewIfNeeded();
  await last.click();
  await expect(page.getByRole('heading', { name: 'bulk-1000' })).toBeVisible();
  expect(await list.evaluate((element) => element.getBoundingClientRect().width)).toBe(width);
});
