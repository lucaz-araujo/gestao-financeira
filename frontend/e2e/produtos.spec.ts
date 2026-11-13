import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

async function login(page: Page, reader = false) {
  await page.goto('/clientes/app/produtos');
  await page.getByLabel('Usuário', { exact: true }).fill((reader ? process.env.E2E_READER_USERNAME : process.env.E2E_USERNAME)!);
  await page.getByLabel('Senha', { exact: true }).fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: /^Produtos/ })).toBeVisible();
}

test('produtos: CRUD, preço, busca, filtro, proteção de vínculos, empresa e mobile', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await login(page);
  await expect(page.getByRole('button', { name: 'Produto empresa Beta', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Novo produto', exact: true }).click();
  await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click();
  await expect(page.getByText('Preencha este campo.', { exact: true }).first()).toBeVisible();
  await page.getByLabel('Descrição', { exact: true }).fill('Produto E2E');
  await page.getByLabel('Sigla', { exact: true }).fill('E2E');
  await page.getByLabel('Valor', { exact: true }).fill('1234,56');
  await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click();
  const row = page.getByRole('row').filter({ hasText: 'Produto E2E' });
  await expect(row).toContainText('1.234,56');
  await expect(page.getByRole('dialog', { name: /cadastro · Produtos/ })).toBeHidden();
  await row.getByRole('button', { name: 'Ver produto', exact: true }).click();
  const details = page.getByRole('dialog', { name: 'Produto E2E', exact: true });
  await expect(details).toContainText('E2E');
  await details.getByRole('button', { name: 'Fechar', exact: true }).click();
  await expect(details).toBeHidden();
  await row.getByRole('button', { name: 'Editar produto', exact: true }).click();
  await page.getByLabel('Descrição', { exact: true }).fill('Produto E2E editado');
  await page.getByLabel('Tipo', { exact: true }).click();
  await page.locator('.ant-select-dropdown:visible').getByText('Serviço', { exact: true }).click();
  await page.getByLabel('Valor', { exact: true }).fill('2345,67');
  await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click();
  await expect(page.getByRole('row').filter({ hasText: 'Produto E2E editado' })).toContainText('2.345,67');
  await expect(page.getByRole('dialog', { name: /cadastro · Produtos/ })).toBeHidden();
  await page.getByRole('combobox', { name: 'Filtrar tipo', exact: true }).click();
  await page.locator('.ant-select-dropdown:visible').getByText('Serviços', { exact: true }).click();
  await expect(page.getByRole('button', { name: 'Licença vinculada', exact: true })).toHaveCount(0);
  await page.getByRole('textbox', { name: 'Buscar produto', exact: true }).fill('E2E');
  await expect(page.getByRole('button', { name: 'Serviço inicial', exact: true })).toHaveCount(0);
  await page.getByRole('row').filter({ hasText: 'Produto E2E editado' }).getByRole('button', { name: 'Excluir produto', exact: true }).click();
  await page.getByRole('button', { name: 'Excluir', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Produto E2E editado', exact: true })).toHaveCount(0);
  await page.getByRole('textbox', { name: 'Buscar produto', exact: true }).fill('');
  await page.getByRole('combobox', { name: 'Filtrar tipo', exact: true }).click();
  await page.locator('.ant-select-dropdown:visible').getByText('Produtos', { exact: true }).click();
  await page.getByRole('row').filter({ hasText: 'Licença vinculada' }).getByRole('button', { name: 'Excluir produto', exact: true }).click();
  await page.getByRole('button', { name: 'Excluir', exact: true }).click();
  await expect(page.getByText('Exclusão impedida: o produto está vinculado a contratos ou liberações.', { exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: 'Empresa ativa', exact: true }).click();
  await page.getByText('Empresa Beta', { exact: true }).click();
  await expect(page.getByRole('button', { name: 'Produto empresa Beta', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Licença vinculada', exact: true })).toHaveCount(0);
  const dir = process.env.E2E_SCREENSHOT_DIR || '/tmp/gestao-produtos-e2e';
  await page.screenshot({ path: dir + '/produtos.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Abrir menu', exact: true }).click();
  await page.getByRole('link', { name: 'Produtos', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(page.locator('.ant-message-notice').last()).toBeHidden();
  await page.screenshot({ path: dir + '/produtos-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test('produtos: conta de consulta não recebe ações de alteração', async ({ page }) => {
  await login(page, true);
  await expect(page.getByRole('button', { name: 'Licença vinculada', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Novo produto', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Editar produto', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Excluir produto', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Clientes', exact: true })).toHaveCount(0);
});
