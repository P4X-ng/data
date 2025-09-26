import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const pageUrl = '/static/transfer-v2.html';

test('transfer-v2 loads and shows key widgets', async ({ page }) => {
  const resp = await page.goto(pageUrl);
  expect(resp?.ok()).toBeTruthy();
  await expect(page.locator('#uploadZone')).toBeVisible();
  await expect(page.getByText('Upload Files')).toBeVisible();
  await expect(page.getByText('Download Files')).toBeVisible();
  await expect(page.locator('#activityLog')).toBeVisible();
});

test('upload small file through UI -> /objects', async ({ page }) => {
  await page.goto(pageUrl);
  const tmp = path.join(process.cwd(), 'tests', 'tmp-upload.bin');
  fs.mkdirSync(path.dirname(tmp), { recursive: true });
  // Create a 5 MiB file to make progress visible
  const size = 5 * 1024 * 1024;
  const buf = Buffer.alloc(size, 0x61);
  fs.writeFileSync(tmp, buf);

  const fileChooserPromise = page.waitForEvent('filechooser');
  await page.locator('#uploadZone').click();
  const chooser = await fileChooserPromise;
  await chooser.setFiles(tmp);

  // Start upload
  const reqPromise = page.waitForResponse(r => r.url().endsWith('/objects') && r.status() === 200);
  await page.locator('#uploadBtn').click();
  const r = await reqPromise;
  const j = await r.json();
  expect(j.object_id).toBeTruthy();

  // Expect a success toast to be visible
  const toast = page.locator('.toast.toast-success').first();
  await expect(toast).toBeVisible();
  // Let the user see it briefly
  await page.waitForTimeout(1500);
});
