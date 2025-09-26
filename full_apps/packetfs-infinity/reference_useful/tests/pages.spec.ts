import { test, expect } from '@playwright/test';

const pages = ['/','/static/index.html','/static/transfer.html'];

for (const p of pages) {
  test(`page loads: ${p}`, async ({ page }) => {
    const resp = await page.goto(p);
    expect(resp?.ok()).toBeTruthy();
    // no severe console errors
    const errors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    await page.waitForLoadState('networkidle');
    expect(errors.join('\n')).toEqual('');
  });
}