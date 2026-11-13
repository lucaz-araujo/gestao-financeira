import { test, expect } from '@playwright/test';
async function login(page: any) {
  await page.goto('/clientes/app/receitas');
  await page.getByLabel('Usuário').fill(process.env.E2E_USERNAME!);
  await page.getByLabel('Senha', { exact: true }).fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: /Contas a receber/ })).toBeVisible();
}
async function select(page: any, label: string, option: string) {
  await page.getByLabel(label, { exact: true }).click();
  await page.locator('.ant-select-dropdown:visible').getByText(option, { exact: false }).click();
  await expect(page.locator('.ant-select-dropdown:visible')).toHaveCount(0);
}
test('recebimento parcial, estorno e conciliação com prévia', async ({ page }) => {
  await login(page);
  await expect(page.getByText('R001', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Ver documento', exact: true }).click();
  await page.getByRole('button', { name: 'Registrar recebimento', exact: true }).click();
  await select(page, 'Conta da baixa', 'Conta A');
  await page.getByLabel('Valor da baixa', { exact: true }).fill('40');
  await page.getByRole('button', { name: 'Confirmar baixa', exact: true }).click();
  await expect(page.getByText('Baixa registrada.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Estornar', exact: true }).click();
  await page.locator('.ant-popover:visible').getByRole('button', { name: 'Estornar', exact: true }).click();
  await expect(page.getByText('Baixa estornada e saldo recalculado.', { exact: false })).toBeVisible();
  await page.locator('.ant-drawer:visible').getByRole('button', { name: 'Fechar', exact: true }).click();
  await page.getByRole('button', { name: 'Conciliar extrato', exact: true }).click();
  await page.getByLabel('Arquivo do extrato').setInputFiles({ name: 'extrato.csv', mimeType: 'text/csv', buffer: Buffer.from('data;valor;documento;historico\n04/11/2026;10,00;BANCO1;Crédito teste\n') });
  await expect(page.getByText('BANCO1', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Confirmar conciliação' })).toBeDisabled();
  await page.screenshot({ path: process.env.E2E_SCREENSHOT_DIR+'/conciliacao.png', fullPage: true });
});
test('despesa React e exportação financeira', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'Contas a pagar', exact: true }).click();
  await page.getByRole('button', { name: 'Nova despesa', exact: true }).click();
  await select(page, 'Fornecedor', 'Fornecedor A');
  await page.getByLabel('Número do documento', { exact: true }).fill('REACT-001');
  await page.getByLabel('Descrição', { exact: true }).fill('Despesa navegador');
  await page.getByLabel('Valor do documento', { exact: true }).fill('123.45');
  await page.getByRole('button', { name: 'Salvar documento', exact: true }).click();
  await expect(page.getByText('Documento salvo.', { exact: true })).toBeVisible();
  await expect(page.getByText('REACT-001', { exact: true })).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exportar CSV', exact: true }).click();
  expect((await download).suggestedFilename()).toBe('despesas.csv');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: process.env.E2E_SCREENSHOT_DIR+'/financeiro-mobile.png', fullPage: true });
});
