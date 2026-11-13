import { readFile } from 'node:fs/promises';
import { test, expect, type Page } from '@playwright/test';
import { savePrintPreview } from './print-helpers';
async function login(page: Page, route: string) {
  await page.goto('/clientes/app/' + route);
  await page.getByLabel('Usuário', { exact: true }).fill(process.env.E2E_USERNAME!);
  await page.getByLabel('Senha', { exact: true }).fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await page.evaluate(() => { window.print = () => {}; });
}
test('impressão: documento financeiro preserva saldos e isola a folha selecionada', async ({ page }) => {
  await login(page, 'receitas');
  await page.getByRole('button', { name: 'Ver documento', exact: true }).click();
  await expect(page.locator('#print-financial-document')).toContainText('R001');
  await page.getByRole('button', { name: 'Imprimir documento', exact: true }).click();
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('.workspace')).toBeHidden();
  await expect(page.locator('#print-financial-document')).toContainText('100,00');
  await expect(page.getByRole('button', { name: 'Estornar', exact: true })).toHaveCount(0);
  await savePrintPreview(page, 'documento-financeiro');
});
test('impressão: relatório A4 com várias páginas e cabeçalhos de tabela', async ({ page }) => {
  await login(page, 'relatorios?tipo=CL');
  const rows = Array.from({ length: 90 }, (_, index) => ({ id: index + 1, instituicao: `Cliente demonstração ${String(index + 1).padStart(3, '0')}`, cnpj: '11.222.333/0001-81', resp_nome: 'Responsável de demonstração', resp_telefone: '85999991111', resp_email: `contato${index + 1}@example.test`, dt_resp_nascimento: '1985-05-20' }));
  await page.route('**/clientes/api/clientes/relatorio/**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ count: rows.length, next: null, previous: null, results: rows }) }));
  await page.getByRole('button', { name: 'Gerar relatório', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Cliente demonstração 090', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Imprimir', exact: true }).click();
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('.report-controls')).toBeHidden();
  await expect(page.locator('.desktop-sidebar')).toBeHidden();
  await savePrintPreview(page, 'relatorio-clientes');
});
test('impressão: análise anual é distribuída por trimestre sem cortar os meses', async ({ page }) => {
  await login(page, 'fechamentos?analise=1');
  const months = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
  const row: Record<string, unknown> = { id: 1, tipo_movimento: 'C', exercicio: 2026, centrocusto: 'Operações', tipodespesa: 'Receitas de demonstração' };
  const totals: Record<string, string> = {};
  for (const [index, month] of months.entries()) { row[month+'p'] = String((index+1)*1000); row[month+'r'] = String((index+1)*900); totals[month+'v'] = String((index+1)*900); }
  await page.route('**/financeiro/api/fechamentos/analise/**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ results: [row], totais: totals }) }));
  await page.getByRole('dialog', { name: 'Análise financeira', exact: true }).getByRole('button', { name: 'Gerar análise', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Análise financeira', exact: true })).toBeHidden();
  await page.getByRole('button', { name: 'Imprimir análise', exact: true }).click();
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('.print-quarter')).toHaveCount(4);
  await expect(page.locator('.analysis-screen').first()).toBeHidden();
  await expect(page.locator('.analysis-screen').last()).toBeHidden();
  await expect(page.locator('.print-quarter').last()).toContainText('DEZ');
  await savePrintPreview(page, 'analise-financeira');
});

test('tabelas: exporta apenas a página atual e imprime uma folha isolada', async ({ page }) => {
  await login(page, 'receitas');
  await expect(page.getByRole('button', { name: 'Imprimir tabela', exact: true })).toBeEnabled();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exportar planilha (CSV)', exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.csv$/);
  const content = await readFile((await download.path())!, 'utf8');
  expect(content).toContain('R001'); expect(content).toContain('100,00');
  expect(content).not.toContain('Ações'); expect(content).not.toContain('Ver documento');
  await page.getByRole('button', { name: 'Imprimir tabela', exact: true }).click();
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('.table-print-snapshot')).toBeVisible();
  await expect(page.locator('.table-print-snapshot')).toContainText('Página 1');
  await expect(page.locator('.workspace')).toBeHidden();
  await savePrintPreview(page, 'tabela-financeira');
  await expect(page.locator('.workspace')).toBeVisible();
  await expect(page.locator('.table-print-snapshot')).toHaveCount(0);
});

test('tabelas: segunda página não exporta registros da primeira', async ({ page }) => {
  await login(page, 'receitas');
  await page.route('**/financeiro/api/receitas/relatorio/**', route => {
    const second = new URL(route.request().url()).searchParams.get('page') === '2';
    const row = { id: second ? 22 : 21, numero: second ? 'PAGINA-DOIS' : 'PAGINA-UM', descricao: 'Filtro de demonstração', parte_nome: 'Cliente teste', valor: '123.45', saldo: '123.45', total_baixado: '0', dt_vencimento: '2026-01-01', situacao_atual: 'Aberto' };
    return route.fulfill({ json: { count: 21, results: [row], next: null, previous: null } });
  });
  await page.getByRole('button', { name: 'Atualizar financeiro', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'PAGINA-UM', exact: true })).toBeVisible();
  await page.locator('.ant-pagination-item-2').click();
  await expect(page.getByRole('cell', { name: 'PAGINA-DOIS', exact: true })).toBeVisible();
  const pending = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exportar planilha (CSV)', exact: true }).click();
  const content = await readFile((await (await pending).path())!, 'utf8');
  expect(content).toContain('PAGINA-DOIS'); expect(content).not.toContain('PAGINA-UM');
  await page.getByRole('button', { name: 'Imprimir tabela', exact: true }).click();
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('.table-print-snapshot')).toContainText('Página 2');
  await expect(page.locator('.table-print-snapshot')).not.toContainText('PAGINA-UM');
});
