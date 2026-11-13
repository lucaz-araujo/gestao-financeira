import { test, expect, type Page } from '@playwright/test';
const nav = (page: Page) => page.locator('.sidebar-navigation:visible');
async function login(page: Page, route = 'clientes', username = process.env.E2E_USERNAME!) {
  await page.goto('/clientes/app/' + route);
  await page.getByLabel('Usuário', { exact: true }).fill(username);
  await page.getByLabel('Senha', { exact: true }).fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(nav(page)).toBeVisible();
}
async function openGroup(page: Page, label: string) {
  const group = nav(page).getByRole('menuitem', { name: label, exact: true });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
}
async function closeDialog(page: Page) {
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: /Fechar|Voltar/, exact: true }).first().click();
  await expect(dialog).toBeHidden();
}

test('menu legado: Cadastro na ordem correta, Contatos, link direto e navegação mobile', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await login(page);
  const cadastro = nav(page).getByRole('menuitem', { name: 'Cadastro', exact: true });
  await expect(cadastro).toHaveAttribute('aria-expanded', 'true');
  await expect(cadastro.locator('..').getByRole('link')).toHaveText(['Parceiros', 'Clientes', 'Bloqueio de clientes', 'Produtos', 'Contatos']);
  await nav(page).getByRole('link', { name: 'Contatos', exact: true }).click();
  await expect(page).toHaveURL(/\/clientes\/app\/agenda$/);
  await expect(page.getByRole('heading', { name: /^Agenda de contatos/ })).toBeVisible();
  await page.goto('/clientes/app/produtos');
  await expect(nav(page).getByRole('link', { name: 'Produtos', exact: true })).toHaveAttribute('aria-current', 'page');
  await page.screenshot({ path: '/tmp/gestao-navigation-e2e/menu.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Abrir menu', exact: true }).click();
  await expect(nav(page).getByRole('menuitem', { name: 'Cadastro', exact: true })).toHaveAttribute('aria-expanded', 'true');
  await openGroup(page, 'Contas Bancos');
  await expect(nav(page).getByRole('link', { name: 'Contas bancárias', exact: true })).toBeVisible();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.screenshot({ path: '/tmp/gestao-navigation-e2e/menu-mobile.png', fullPage: true });
  await nav(page).getByRole('link', { name: 'Contas bancárias', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(page.getByRole('heading', { name: /^Contas bancárias/ })).toBeVisible();
  expect(errors).toEqual([]);
});

test('menu legado: relatórios hierárquicos aplicam o tipo ao trocar de atalho e conciliação abre revisão', async ({ page }) => {
  await login(page, 'receitas');
  await openGroup(page, 'Relatórios'); await openGroup(page, 'Cadastrais');
  await nav(page).getByRole('link', { name: 'Relatório de clientes', exact: true }).click();
  const reportSelect = page.locator('.ant-select').filter({ has: page.getByLabel('Relatório', { exact: true }) });
  await expect(reportSelect).toContainText('Clientes');
  await nav(page).getByRole('link', { name: 'Relatório de parceiros', exact: true }).click();
  await expect(reportSelect).toContainText('Parceiros');
  await expect(nav(page).getByRole('link', { name: 'Relatório de parceiros', exact: true })).toHaveAttribute('aria-current', 'page');
  await openGroup(page, 'Financeiros');
  await nav(page).getByRole('link', { name: 'Inadimplentes', exact: true }).click();
  await expect(page).toHaveURL(/situacao=vencido/);
  await expect(page.getByRole('heading', { name: /^Contas a receber/ })).toBeVisible();
  await openGroup(page, 'Financeiro');
  await nav(page).getByRole('link', { name: 'Conciliação bancária', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Conciliar extrato', exact: true })).toBeVisible();
  await closeDialog(page);
  await openGroup(page, 'Relatórios'); await openGroup(page, 'Financeiros');
  await nav(page).getByRole('link', { name: 'Cheques emitidos', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Gerar relatório', exact: true })).toBeVisible();
  await expect(page.locator('.ant-select').filter({ has: page.getByLabel('Tipo de relatório', { exact: true }) })).toContainText('Cheques emitidos');
  await closeDialog(page);
  await openGroup(page, 'Relatórios'); await openGroup(page, 'Bancários');
  await nav(page).getByRole('link', { name: 'Relatório de lançamentos bancários', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Gerar relatório', exact: true })).toBeVisible();
  await expect(page.locator('.ant-select').filter({ has: page.getByLabel('Tipo de relatório', { exact: true }) })).toContainText('Movimentações');
});

test('menu legado: conta autorizada somente a contatos recebe Cadastro sem módulos indevidos', async ({ page }) => {
  await login(page, 'agenda', process.env.E2E_CONTACT_USERNAME!);
  await expect(nav(page).getByRole('link', { name: 'Contatos', exact: true })).toBeVisible();
  for (const label of ['Clientes', 'Parceiros', 'Produtos', 'Bloqueio de clientes']) await expect(nav(page).getByRole('link', { name: label, exact: true })).toHaveCount(0);
  for (const label of ['Financeiro', 'Movimento', 'Compras', 'Relatórios', 'Configurações']) await expect(nav(page).getByRole('menuitem', { name: label, exact: true })).toHaveCount(0);
});
