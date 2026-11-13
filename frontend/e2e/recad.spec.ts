import { test, expect, type Page } from '@playwright/test';
async function login(page: Page, username = process.env.E2E_USERNAME!) {
  await page.goto('/clientes/app/recadastramento');
  await page.getByLabel('Usuário', { exact: true }).fill(username);
  await page.getByLabel('Senha', { exact: true }).fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Recadastramento', exact: true })).toBeVisible();
}
async function tab(page: Page, name: string) { await page.getByRole('tab', { name, exact: true }).click(); await expect(page.getByRole('heading', { name: new RegExp('^' + name) })).toBeVisible(); }
async function save(page: Page) { await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click(); await expect(page.getByRole('dialog', { name: /^Cadastro —/ })).toBeHidden(); }
async function remove(page: Page, name: string) { await page.getByRole('row').filter({ hasText: name }).getByRole('button', { name: 'Excluir', exact: true }).click(); await page.getByRole('dialog').getByRole('button', { name: 'Excluir', exact: true }).click(); }
const roles = ['Usuários da entidade', 'Contadores', 'Controladores', 'Prefeitos', 'Vice-prefeitos'];

test('recadastramento: entidade e cinco responsáveis, edição, proteção, exclusão, empresa e mobile', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message)); await login(page);
  await expect(page.getByRole('cell', { name: 'Entidade Beta', exact: true })).toHaveCount(0);
  await expect(page.getByRole('cell', { name: 'Entidade PI', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Novo cadastro', exact: true }).click();
  await page.getByLabel('Cliente', { exact: true }).click();
  await page.locator('.ant-select-dropdown:visible').getByText('Cliente Alfa', { exact: true }).click();
  await page.getByLabel('Nome da entidade', { exact: true }).fill('Nova Entidade');
  await page.getByLabel('Código', { exact: true }).fill('1234');
  await page.getByLabel('Telefone', { exact: true }).fill('85999991111');
  await page.getByLabel('E-mail', { exact: true }).fill('entidade-nova@example.test');
  await save(page); await expect(page.getByRole('cell', { name: 'Nova Entidade', exact: true })).toBeVisible();
  for (const [index, role] of roles.entries()) {
    await tab(page, role); await page.getByRole('button', { name: 'Novo cadastro', exact: true }).click();
    await page.getByLabel('Entidade', { exact: true }).click();
    await page.locator('.ant-select-dropdown:visible').getByText('Nova Entidade', { exact: true }).click();
    await expect(page.locator('.ant-select').filter({ has: page.getByLabel('Entidade', { exact: true }) })).toContainText('Nova Entidade');
    await page.getByLabel('Nome completo', { exact: true }).fill('Responsável ' + index);
    if (index === 0) await page.getByLabel('Cargo', { exact: true }).fill('Operador');
    await page.getByLabel('E-mail', { exact: true }).fill(`responsavel${index}@example.test`);
    await save(page);
    const row = page.getByRole('row').filter({ hasText: 'Responsável ' + index }); await expect(row).toBeVisible();
    await row.getByRole('button', { name: 'Editar', exact: true }).click();
    await expect(page.getByRole('dialog', { name: /^Cadastro —/ })).toBeVisible();
    await expect(page.getByLabel('Nome completo', { exact: true })).toHaveValue('Responsável ' + index);
    await page.getByLabel('Nome completo', { exact: true }).fill('Responsável editado ' + index); await save(page);
    await expect(page.getByRole('cell', { name: 'Responsável editado ' + index, exact: true })).toBeVisible();
  }
  await tab(page, 'Entidades'); await remove(page, 'Nova Entidade');
  await expect(page.getByText('O registro possui vínculos ou um conflito de integridade. Os dados foram preservados.', { exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'Nova Entidade', exact: true })).toBeVisible();
  for (const [index, role] of roles.entries()) { await tab(page, role); await remove(page, 'Responsável editado ' + index); await expect(page.getByRole('cell', { name: 'Responsável editado ' + index, exact: true })).toHaveCount(0); }
  await tab(page, 'Entidades'); await remove(page, 'Nova Entidade'); await expect(page.getByRole('cell', { name: 'Nova Entidade', exact: true })).toHaveCount(0);
  await page.getByRole('row').filter({ hasText: 'Entidade Alfa' }).getByRole('button', { name: 'Ver', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Detalhes do recadastramento', exact: true })).toContainText('entidade@example.test');
  const detail = page.getByRole('dialog', { name: 'Detalhes do recadastramento', exact: true });
  await detail.getByRole('button', { name: 'Fechar', exact: true }).click();
  await expect(detail).toBeHidden();
  await page.getByRole('combobox', { name: 'Empresa ativa', exact: true }).click();
  await page.locator('.ant-select-dropdown:visible').getByText('Empresa Beta', { exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Entidade Beta', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'Entidade Alfa', exact: true })).toHaveCount(0);
  await page.screenshot({ path: '/tmp/gestao-recad-e2e/recad.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 }); await page.screenshot({ path: '/tmp/gestao-recad-e2e/recad-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true); expect(errors).toEqual([]);
});

test('recadastramento: consulta de entidades não permite escrita nem expõe contatos pessoais', async ({ page }) => {
  await login(page, process.env.E2E_READER_USERNAME!);
  await expect(page.getByRole('cell', { name: 'Entidade Alfa', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Novo cadastro', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Editar', exact: true })).toHaveCount(0);
  await expect(page.getByRole('tab', { name: 'Usuários da entidade', exact: true })).toHaveCount(0);
  expect((await page.request.get('/recadclientes/api/usuarios/')).status()).toBe(403);
});

test('recadastramento: permissão de contador funciona sem acesso ao cadastro da entidade', async ({ page }) => {
  await login(page, process.env.E2E_CHILD_USERNAME!);
  await expect(page.getByRole('cell', { name: 'Contador de teste', exact: true })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Entidades', exact: true })).toHaveCount(0);
  expect((await page.request.get('/recadclientes/api/entidades/')).status()).toBe(403);
});
