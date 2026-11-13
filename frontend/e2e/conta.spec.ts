import { savePrintPreview } from './print-helpers';
import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
async function login(page: Page, reader = false) {
  await page.goto('/clientes/app/contas');
  await page.getByLabel('Usuário', { exact: true }).fill((reader ? process.env.E2E_READER_USERNAME : process.env.E2E_USERNAME)!);
  await page.getByLabel('Senha', { exact: true }).fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: /^Contas bancárias/ })).toBeVisible();
}
function row(page: Page, value: string) { return page.locator('section.table-panel.print-hidden').getByRole('row').filter({ hasText: value }); }
async function select(page: Page, label: string, option: string | RegExp) {
  await page.getByLabel(label, { exact: true }).click();
  await page.locator('.ant-select-dropdown:visible').getByText(option, { exact: typeof option === 'string' }).click();
  await expect(page.locator('.ant-select-dropdown:visible')).toHaveCount(0);
}
async function save(page: Page) {
  await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click();
  await expect(page.getByRole('dialog', { name: /cadastro ·/ })).toBeHidden();
}
async function remove(page: Page, target: ReturnType<typeof row>, name: string) {
  await target.getByRole('button', { name, exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Excluir', exact: true }).click();
  await expect(target).toHaveCount(0);
}
test('contas: catálogo, cadastro bancário, edição, detalhes e exclusão', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'Bancos', exact: true }).click();
  await page.getByRole('button', { name: 'Novo banco', exact: true }).click();
  await page.getByLabel('Código do banco', { exact: true }).fill('777');
  await page.getByLabel('Nome do banco', { exact: true }).fill('Banco E2E');
  await save(page);
  await expect(row(page, 'Banco E2E')).toBeVisible();
  await page.getByRole('link', { name: 'Contas bancárias', exact: true }).click();
  await page.getByRole('button', { name: 'Nova conta', exact: true }).click();
  await page.getByLabel('Descrição da conta', { exact: true }).fill('Conta E2E');
  await select(page, 'Banco', '777-Banco E2E');
  await page.getByLabel('Agência', { exact: true }).fill('0001');
  await page.getByLabel('Dígito da agência', { exact: true }).fill('X');
  await page.getByLabel('Número da conta', { exact: true }).fill('007001');
  await page.getByLabel('Dígito da conta', { exact: true }).fill('0');
  await select(page, 'Plano de contas', '1.1-Caixa');
  await save(page);
  await expect(row(page, 'Conta E2E')).toContainText('007001-0');
  await row(page, 'Conta E2E').getByRole('button', { name: 'Editar conta', exact: true }).click();
  await expect(page.getByLabel('Número da conta', { exact: true })).toHaveValue('007001');
  await page.getByLabel('Descrição da conta', { exact: true }).fill('Conta editada');
  await save(page);
  await row(page, 'Conta editada').getByRole('button', { name: 'Ver conta', exact: true }).click();
  const details = page.getByRole('dialog', { name: 'Detalhes · Contas bancárias' });
  await expect(details).toContainText('Caixa');
  await details.getByRole('button', { name: 'Fechar', exact: true }).click();
  await expect(details).toBeHidden();
  await remove(page, row(page, 'Conta editada'), 'Excluir conta');
  await page.getByRole('link', { name: 'Bancos', exact: true }).click();
  await remove(page, row(page, 'Banco E2E'), 'Excluir banco');
});

test('contas: movimentos, período fechado, transferência pareada, extrato, CSV, impressão e empresa', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  await login(page);
  await page.getByRole('link', { name: 'Movimentações', exact: true }).click();
  await page.getByRole('button', { name: 'Novo movimento', exact: true }).click();
  await select(page, 'Conta bancária', / - Origem$/);
  await page.getByLabel('Valor', { exact: true }).fill('1,234');
  await page.getByLabel('Número do documento', { exact: true }).fill('MANUAL-E2E');
  await save(page);
  await expect(row(page, 'MANUAL-E2E')).toContainText('1,234');
  await row(page, 'MANUAL-E2E').getByRole('button', { name: 'Editar movimento', exact: true }).click();
  await page.getByLabel('Valor', { exact: true }).fill('2,345');
  await save(page);
  await expect(row(page, 'MANUAL-E2E')).toContainText('2,345');
  await page.getByRole('button', { name: 'Novo movimento', exact: true }).click();
  await select(page, 'Conta bancária', / - Fechada$/);
  await page.getByLabel('Valor', { exact: true }).fill('1');
  await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click();
  await expect(page.getByText(/O período está fechado em pelo menos uma das contas/)).toBeVisible();
  await page.getByRole('dialog', { name: /cadastro ·/ }).getByRole('button', { name: 'Fechar', exact: true }).click();
  await expect(page.getByRole('dialog', { name: /cadastro ·/ })).toBeHidden();
  await page.getByRole('link', { name: 'Transferências', exact: true }).click();
  await page.getByRole('button', { name: 'Nova transferência', exact: true }).click();
  await select(page, 'Conta de origem', / - Origem$/);
  await select(page, 'Conta de destino', / - Destino$/);
  await page.getByLabel('Valor', { exact: true }).fill('10,001');
  await page.getByLabel('Número do documento', { exact: true }).fill('TR-E2E');
  await save(page);
  await expect(row(page, 'TR-E2E')).toContainText('Consistentes');
  await row(page, 'TR-E2E').getByRole('button', { name: 'Editar transferência', exact: true }).click();
  await page.getByLabel('Valor', { exact: true }).fill('20,456');
  await save(page);
  await expect(row(page, 'TR-E2E')).toContainText('20,456');
  await page.getByRole('link', { name: 'Movimentações', exact: true }).click();
  await expect(row(page, 'TR-E2E')).toHaveCount(2);
  await expect(row(page, 'TR-E2E').getByRole('button', { name: 'Editar movimento' })).toHaveCount(0);
  await expect(row(page, 'TR-E2E').getByRole('button', { name: 'Excluir movimento' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Relatórios e extrato', exact: true }).click();
  await select(page, 'Tipo de relatório', 'Extrato por conta');
  await select(page, 'Conta do relatório', / - Origem$/);
  await page.getByRole('button', { name: 'Gerar relatório', exact: true }).click();
  const report = page.locator('.report-output');
  await expect(report).toContainText('Extrato da conta');
  await expect(report.getByText('Saldo final:')).toContainText('8,111');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exportar CSV' }).click();
  expect((await download).suggestedFilename()).toBe('relatorio-movimentos.csv');
  await page.evaluate(() => { window.print = () => { document.body.dataset.printed = 'yes'; }; });
  await page.getByRole('button', { name: 'Imprimir relatório' }).click();
  await expect(page.locator('body')).toHaveAttribute('data-printed', 'yes');
  await page.emulateMedia({ media: 'print' });
  await expect(report).toBeVisible();
  await expect(page.locator('section.table-panel.print-hidden')).toBeHidden();
  await savePrintPreview(page, 'extrato-bancario');
  await page.emulateMedia({ media: 'screen' });
  await page.screenshot({ path: process.env.E2E_SCREENSHOT_DIR + '/extrato.png', fullPage: true });
  await page.getByRole('link', { name: 'Transferências', exact: true }).click();
  await remove(page, row(page, 'TR-E2E'), 'Excluir transferência');
  await page.getByRole('link', { name: 'Movimentações', exact: true }).click();
  await expect(row(page, 'TR-E2E')).toHaveCount(0);
  await remove(page, row(page, 'MANUAL-E2E'), 'Excluir movimento');
  await page.getByRole('link', { name: 'Contas bancárias', exact: true }).click();
  await page.getByRole('combobox', { name: 'Empresa ativa', exact: true }).click();
  await page.locator('.ant-select-dropdown:visible').getByText('Empresa Beta', { exact: true }).click();
  await expect(page.locator('.ant-select-dropdown:visible')).toHaveCount(0);
  await expect(row(page, 'Conta Beta')).toBeVisible();
  await expect(row(page, 'Origem')).toHaveCount(0);
  await expect(page.locator('.ant-message-notice').last()).toBeHidden();
  await page.screenshot({ path: process.env.E2E_SCREENSHOT_DIR + '/contas.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: process.env.E2E_SCREENSHOT_DIR + '/contas-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test('contas: leitor consulta sem botões de escrita', async ({ page }) => {
  await login(page, true);
  await expect(page.getByRole('button', { name: 'Nova conta', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Editar conta', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Excluir conta', exact: true })).toHaveCount(0);
  await page.getByRole('link', { name: 'Transferências', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Nova transferência', exact: true })).toHaveCount(0);
  await page.getByRole('link', { name: 'Movimentações', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Novo movimento', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Editar movimento', exact: true })).toHaveCount(0);
});
