import { test, expect, type Page } from '@playwright/test';

async function login(page: Page, username = process.env.E2E_USERNAME!) {
  await page.goto('/dashboard/');
  await page.getByLabel('Usuário', { exact: true }).fill(username);
  await page.getByLabel('Senha', { exact: true }).fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
}
const card = (page: Page, title: string) => page.locator('.ant-card').filter({ has: page.getByText(title, { exact: true }) });

test('dashboard: indicadores reais, competência persistida, empresa, estado vazio e mobile', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await login(page);
  await expect(page.getByRole('heading', { name: 'Visão geral', exact: true })).toBeVisible();
  await expect(card(page, 'Clientes cadastrados').locator('.ant-statistic-content')).toHaveText('2');
  await expect(card(page, 'Notas na competência').locator('.ant-statistic-content')).toHaveText('2');
  await expect(page.locator('.ant-statistic').filter({ has: page.getByText('Saldo a receber', { exact: true }) })).toContainText('50,00');
  await expect(page.getByRole('cell', { name: 'CON-ALFA', exact: true })).toBeVisible();
  await expect(page.getByText('Cliente PI', { exact: true })).toHaveCount(0);
  const month = page.getByRole('combobox', { name: 'Mês do painel', exact: true });
  await month.click();
  for (let step = 0; step < 9; step++) await month.press('ArrowUp');
  await month.press('Enter');
  await expect(page.locator('.ant-select').filter({ has: month })).toContainText('Fevereiro');
  await page.getByRole('spinbutton', { name: 'Exercício do painel', exact: true }).fill('2027');
  await page.getByRole('button', { name: 'Aplicar competência', exact: true }).click();
  await expect(page.getByText('Competência atualizada.', { exact: true })).toBeVisible();
  await expect(card(page, 'Notas na competência').locator('.ant-statistic-content')).toHaveText('0');
  await page.reload();
  await expect(page.getByRole('spinbutton', { name: 'Exercício do painel', exact: true })).toHaveValue('2027');
  await expect(card(page, 'Notas na competência').locator('.ant-statistic-content')).toHaveText('0');
  const response = await page.request.get('/dashboard/api/competencia/');
  expect(await response.json()).toEqual({ mes: 2, ano: 2027 });
  await page.getByRole('combobox', { name: 'Empresa ativa', exact: true }).click();
  await page.locator('.ant-select-dropdown:visible').getByText('Empresa Beta', { exact: true }).click();
  await expect(card(page, 'Clientes cadastrados').locator('.ant-statistic-content')).toHaveText('1');
  await page.getByRole('combobox', { name: 'Empresa ativa', exact: true }).click();
  await page.locator('.ant-select-dropdown:visible').getByText('Empresa Vazia', { exact: true }).click();
  await expect(card(page, 'Clientes cadastrados').locator('.ant-statistic-content')).toHaveText('0');
  await expect(page.getByText('Nenhum cliente vinculado a parceiro autorizado.', { exact: true })).toBeVisible();
  await page.screenshot({ path: '/tmp/gestao-dashboard-e2e/dashboard.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '/tmp/gestao-dashboard-e2e/dashboard-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test('dashboard: leitor de notas não recebe clientes, receitas, parceiros ou contratos', async ({ page }) => {
  await login(page, process.env.E2E_READER_USERNAME!);
  await expect(card(page, 'Notas na competência')).toBeVisible();
  await expect(page.getByText('Clientes cadastrados', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Receitas com vencimento no mês', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Vencimentos de contratos', { exact: true })).toHaveCount(0);
  const response = await page.request.get('/dashboard/api/resumo/'); expect(response.status()).toBe(200);
  const data = await response.json();
  for (const key of ['clientes', 'receitas', 'parceiros', 'alertas']) expect(data[key]).toBeNull();
  expect((await page.request.get('/dashboard/api/resumo/', { headers: { 'X-Empresa-ID': '999999' } })).status()).toBe(403);
});

test('dashboard: conta sem permissões mantém perfil e API do painel responde 403', async ({ page }) => {
  await page.goto('/clientes/app/perfil');
  await page.getByLabel('Usuário', { exact: true }).fill(process.env.E2E_PROFILE_USERNAME!);
  await page.getByLabel('Senha', { exact: true }).fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Meu perfil', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Visão geral', exact: true })).toHaveCount(0);
  expect((await page.request.get('/dashboard/api/resumo/')).status()).toBe(403);
});
