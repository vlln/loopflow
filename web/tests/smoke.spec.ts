import { expect, test } from '@playwright/test';

test('launches Chromium and renders a non-empty page', async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'reduce', colorScheme: 'dark' });
  await page.goto('/');

  const root = page.getByTestId('infrastructure-smoke');
  await expect(root).toBeVisible();
  await expect(page.getByRole('heading', { name: 'loopflow' })).toBeVisible();

  const pixels = await root.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return { width: rect.width, height: rect.height };
  });
  expect(pixels.width).toBeGreaterThan(0);
  expect(pixels.height).toBeGreaterThan(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    await page.evaluate(() => document.documentElement.clientWidth),
  );
  await page.screenshot({ path: testInfo.outputPath('smoke.png'), fullPage: true });
});
