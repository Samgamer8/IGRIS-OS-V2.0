import { test, expect } from '@playwright/test';
import { readFileSync, existsSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const repository = fileURLToPath(new URL('../../../', import.meta.url));
const settings = path.join(repository, 'runtime/settings.json');
const checksum = () => existsSync(settings) ? createHash('sha256').update(readFileSync(settings)).digest('hex') : null;

test('original pixels are preserved and visual edits export without changing IGRIS', async ({ page }) => {
  const before = checksum();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:5185/');
  await page.waitForFunction(() => window.__panelStudio?.ready);
  expect(await page.evaluate(() => window.__panelStudio.mode)).toBe('original');
  const equal = await page.evaluate(async () => {
    const image = new Image(); image.src = '/reference/original.png'; await image.decode();
    const reference = document.createElement('canvas'); reference.width = 1440; reference.height = 810;
    const context = reference.getContext('2d'); context.drawImage(image, 0, 0, 1440, 810);
    const expected = context.getImageData(0, 0, 1440, 810).data;
    const actual = window.__panelStudio.canvas.getContext('2d').getImageData(0, 0, 1440, 810).data;
    for (let index = 0; index < expected.length; index += 997) if (expected[index] !== actual[index]) return false;
    return true;
  });
  expect(equal).toBe(true);
  await page.locator('[data-setting="chat"]').focus();
  await page.locator('[data-setting="chat"]').press('End');
  expect(await page.evaluate(() => window.__panelStudio.design.chat)).toBe(560);
  expect(await page.evaluate(() => window.__panelStudio.mode)).toBe('proposal');
  await page.locator('#save-draft').click();
  await expect(page.locator('#notice')).toContainText('Borrador guardado');
  const downloadPromise = page.waitForEvent('download');
  await page.locator('#export-image').click();
  const download = await downloadPromise;
  mkdirSync('evidence', { recursive: true });
  await download.saveAs('evidence/panel-propuesta.png');
  expect(readFileSync('evidence/panel-propuesta.png').subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))).toBe(true);
  await page.reload(); await page.waitForFunction(() => window.__panelStudio?.ready);
  expect(await page.evaluate(() => window.__panelStudio.design.chat)).toBe(560);
  await page.locator('[data-view="proposal"]').click();
  await page.screenshot({ path: 'evidence/editor-desktop.png', fullPage: true });
  expect(errors).toEqual([]);
  expect(checksum()).toBe(before);
});

test('mobile layout remains usable without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('http://127.0.0.1:5185/');
  await page.waitForFunction(() => window.__panelStudio?.ready);
  await page.locator('[data-view="proposal"]').click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const colors = await page.evaluate(() => {
    const data = window.__panelStudio.canvas.getContext('2d').getImageData(500, 250, 64, 64).data;
    const colors = new Set();
    for (let index = 0; index < data.length; index += 4) colors.add(`${data[index]},${data[index + 1]},${data[index + 2]}`);
    return colors.size;
  });
  expect(colors).toBeGreaterThan(15);
  mkdirSync('evidence', { recursive: true });
  await page.screenshot({ path: 'evidence/editor-mobile.png', fullPage: true });
});