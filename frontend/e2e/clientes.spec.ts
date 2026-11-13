import { test, expect } from '@playwright/test';
import type { Page, Locator } from '@playwright/test';
const screenshotDir = process.env.E2E_SCREENSHOT_DIR || '/tmp/gestao-clientes-e2e';
async function settleDialog(dialog: Locator) {
  await dialog.evaluate(async node => {
    await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
    await Promise.all((node.closest('.ant-modal') ?? node).getAnimations({ subtree: true }).map(animation => animation.finished.catch(() => {})));
  });
}

async function fillRegistration(page: Page, name: string, partner = false) {
  await page.getByLabel('Instituição', { exact: true }).fill(name);
  await page.getByLabel('CNPJ', { exact: true }).fill('11.222.333/0001-81');
  await page.getByLabel('Endereço', { exact: true }).fill('Rua da Integração');
  await page.getByLabel('Número', { exact: true }).fill('100');
  await page.getByLabel('Bairro', { exact: true }).fill('Centro');
  await page.getByLabel('CEP', { exact: true }).fill('60000-000');
  await page.getByLabel('UF', { exact: true }).click();
  await page.getByText('CE — Ceará', { exact: true }).click();
  if (partner) {
    await page.getByLabel('Município', { exact: true }).click();
    await page.getByText('Fortaleza', { exact: true }).click();
  } else {
    await page.getByLabel(/^Código Layout/).fill('0001');
    await page.getByLabel(/^Código da entidade/).fill('01');
  }
}
test('fluxo completo com PostgreSQL: login, CRUD, liberação, bloqueio, relatórios e empresa', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/clientes/app/clientes');
  await expect(page.getByRole('button', { name: 'Entrar', exact: true })).toBeVisible();
  await page.screenshot({ path: screenshotDir + '/login.png', fullPage: true });
  await page.getByLabel('Usuário', { exact: true }).fill(process.env.E2E_USERNAME!);
  await page.getByLabel('Senha', { exact: true }).fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: /Clientes/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Cliente de outra empresa', exact: true })).toHaveCount(0);
  await page.screenshot({ path: screenshotDir + '/clientes.png', fullPage: true });
  // Os tokens não são persistidos em armazenamento acessível ao JavaScript.
  expect(await page.evaluate(() => Object.keys(localStorage).filter(k => /token|access|refresh/i.test(k)))).toEqual([]);
  const cookie = (await page.context().cookies()).find(c => c.name === 'clientes_refresh');
  expect(cookie?.httpOnly).toBe(true);
  await page.reload();
  await expect(page.getByRole('heading', { name: /Clientes/ })).toBeVisible();
  // Acesso expirado: a API renova e repete a leitura automaticamente.
  let expired = false;
  await page.route('**/clientes/api/clientes/?*', async route => {
    if (!expired) { expired = true; await route.fulfill({ status: 401, contentType: 'application/json', body: '{"code":"token_not_valid"}' }); }
    else await route.continue();
  });
  const refresh = page.waitForResponse(r => r.url().includes('/auth/refresh/') && r.status() === 200);
  await page.getByRole('button', { name: 'Atualizar lista', exact: true }).click();
  await refresh;
  await page.unroute('**/clientes/api/clientes/?*');
  await page.getByRole('link', { name: 'Parceiros', exact: true }).click();
  await page.getByRole('button', { name: 'Novo parceiro', exact: true }).click();
  await fillRegistration(page, 'Parceiro E2E', true);
  await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Parceiro E2E', exact: true })).toBeVisible();
  // Erros de validação devolvidos pela API aparecem no formulário React.
  await page.getByRole('button', { name: 'Novo parceiro', exact: true }).click();
  await fillRegistration(page, 'Parceiro duplicado', true);
  await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click();
  await expect(page.getByText('Este CNPJ já está informado.', { exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Cancelar', exact: true }).click();
  await page.getByRole('link', { name: 'Clientes', exact: true }).click();
  await page.getByRole('button', { name: 'Novo cliente', exact: true }).click();
  await fillRegistration(page, 'Cliente E2E');
  await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Cliente E2E', exact: true })).toBeVisible();
  const row = page.getByRole('row').filter({ hasText: 'Cliente E2E' });
  await row.getByRole('button', { name: 'Editar cliente' }).click();
  await page.getByLabel('Instituição', { exact: true }).fill('Cliente E2E atualizado');
  await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Cliente E2E atualizado', exact: true })).toBeVisible();
  await page.getByRole('menuitem', { name: 'Financeiro', exact: true }).click();
  await page.getByRole('link', { name: 'Liberações', exact: true }).click();
  await page.getByRole('button', { name: 'Nova liberação', exact: true }).click();
  await page.getByLabel('Cliente', { exact: true }).click();
  await page.getByText('Cliente E2E atualizado', { exact: true }).click();
  await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Cliente E2E atualizado', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Bloqueio de clientes', exact: true }).click();
  await page.getByRole('button', { name: 'Novo bloqueio', exact: true }).click();
  await page.getByLabel('Cliente', { exact: true }).click();
  await page.getByText('Cliente E2E atualizado', { exact: true }).click();
  await page.getByLabel('Data inicial', { exact: true }).fill('01/10/2026');
  await page.getByLabel('Data inicial', { exact: true }).press('Enter');
  await page.getByLabel('Data final', { exact: true }).fill('31/10/2026');
  await page.getByLabel('Data final', { exact: true }).press('Enter');
  await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Cliente E2E atualizado', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Editar bloqueio', exact: true }).click();
  await page.getByLabel(/^Sistema/).click();
  await page.getByRole('button', { name: 'Salvar cadastro', exact: true }).click();
  await expect(page.getByText('Liberado', { exact: true })).toBeVisible();
  await page.getByRole('menuitem', { name: 'Relatórios', exact: true }).click();
  await page.getByRole('link', { name: 'Todos os relatórios cadastrais e fiscais', exact: true }).click();
  await page.getByRole('button', { name: 'Gerar relatório', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Cliente E2E atualizado', exact: true })).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exportar CSV' }).click();
  expect((await download).suggestedFilename()).toBe('relatorio-clientes.csv');
  await page.getByRole('link', { name: 'Clientes', exact: true }).click();
  let deleteRequests = 0;
  page.on('request', request => { if (request.method() === 'DELETE') deleteRequests++; });
  const deleteTrigger = page.getByRole('row').filter({ hasText: 'Cliente E2E atualizado' }).getByRole('button', { name: 'Excluir cliente' });
  await deleteTrigger.click();
  const deletion = page.getByRole('dialog', { name: 'Excluir cliente?', exact: true });
  await expect(deletion).toBeVisible();
  await settleDialog(deletion);
  await expect(deletion).toContainText('Cliente E2E atualizado');
  await expect(deletion.getByRole('button', { name: 'Cancelar', exact: true })).toBeFocused();
  await expect.poll(async () => {
    const box = await deletion.boundingBox(), viewport = page.viewportSize()!;
    return box ? Math.max(Math.abs(box.x + box.width / 2 - viewport.width / 2), Math.abs(box.y + box.height / 2 - viewport.height / 2)) : 999;
  }).toBeLessThan(8);
  await page.mouse.click(8, 100);
  await expect(deletion).toBeVisible();
  await page.screenshot({ path: screenshotDir + '/excluir-centralizado.png', fullPage: true, animations: 'disabled' });
  await deletion.getByRole('button', { name: 'Cancelar', exact: true }).click();
  await expect(deletion).toBeHidden();
  expect(deleteRequests).toBe(0);
  await expect(deleteTrigger).toBeVisible();
  await deleteTrigger.click();
  await page.getByRole('button', { name: 'Excluir', exact: true }).click();
  await expect(page.getByText('Exclusão impedida: existem registros vinculados.', { exact: true })).toBeVisible();
  // Trocar a empresa descarta a tela e recarrega o conjunto autorizado.
  await page.getByRole('combobox', { name: 'Empresa ativa', exact: true }).click();
  await page.getByText('Empresa Beta', { exact: true }).click();
  await expect(page.getByRole('button', { name: 'Cliente de outra empresa', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Cliente E2E atualizado', exact: true })).toHaveCount(0);
  await page.getByRole('combobox', { name: 'Empresa ativa', exact: true }).click();
  await page.getByText('Empresa Alfa', { exact: true }).click();
  // Remover dependentes e concluir a exclusão do cadastro.
  for (const [section, label] of [['Bloqueio de clientes', 'Excluir bloqueio'], ['Liberações', 'Excluir liberação']]) {
    await page.getByRole('link', { name: section, exact: true }).click();
    await page.getByRole('button', { name: label, exact: true }).click();
    await page.getByRole('button', { name: 'Excluir', exact: true }).click();
    await expect(page.getByRole('cell', { name: 'Cliente E2E atualizado', exact: true })).toHaveCount(0);
  }
  await page.getByRole('link', { name: 'Clientes', exact: true }).click();
  await page.getByRole('row').filter({ hasText: 'Cliente E2E atualizado' }).getByRole('button', { name: 'Excluir cliente' }).click();
  await page.getByRole('button', { name: 'Excluir', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Cliente E2E atualizado', exact: true })).toHaveCount(0);
  await page.getByRole('link', { name: 'Parceiros', exact: true }).click();
  await page.getByRole('button', { name: 'Excluir parceiro', exact: true }).click();
  await page.getByRole('button', { name: 'Excluir', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Parceiro E2E', exact: true })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Abrir menu' }).click();
  await page.getByRole('link', { name: 'Clientes', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(page.getByRole('button', { name: 'Município de Fortaleza', exact: true })).toBeVisible();
  await page.getByRole('row').filter({ hasText: 'Município de Fortaleza' }).getByRole('button', { name: 'Excluir cliente', exact: true }).click();
  const mobileDeletion = page.getByRole('dialog', { name: 'Excluir cliente?', exact: true });
  await expect(mobileDeletion).toBeVisible();
  await settleDialog(mobileDeletion);
  await expect.poll(async () => {
    const box = await mobileDeletion.boundingBox(), viewport = page.viewportSize()!;
    return box ? Math.max(Math.abs(box.x + box.width / 2 - viewport.width / 2), Math.abs(box.y + box.height / 2 - viewport.height / 2)) : 999;
  }).toBeLessThan(8);
  await page.screenshot({ path: screenshotDir + '/excluir-centralizado-mobile.png', fullPage: true, animations: 'disabled' });
  await page.keyboard.press('Escape');
  await expect(mobileDeletion).toBeHidden();
  await expect(page.locator('.ant-message-notice').last()).toBeHidden();
  await page.screenshot({ path: screenshotDir + '/mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Sair', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Entrar', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Entrar', exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
