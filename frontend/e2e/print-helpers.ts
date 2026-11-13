import { expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
export async function savePrintPreview(page: Page, name: string) {
  const directory = '/tmp/gestao-print-e2e'; await mkdir(directory, { recursive: true });
  await page.emulateMedia({ media: 'print' });
  const sheet = page.locator('[data-layout-print-target], .public-print-document .print-page');
  await expect(sheet).toBeVisible();
  await expect(sheet.getByAltText('Layout Sistemas').first()).toBeVisible();
  await page.screenshot({ path: `${directory}/${name}.png`, fullPage: true });
  await page.pdf({ path: `${directory}/${name}.pdf`, preferCSSPageSize: true, printBackground: true, displayHeaderFooter: false });
  await page.emulateMedia({ media: 'screen' });
}
