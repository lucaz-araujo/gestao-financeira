import { test, expect, type Page } from '@playwright/test';
async function login(page:Page,username=process.env.E2E_USERNAME!){
 await page.goto('/clientes/app/empresas');await page.getByLabel('Usuário',{exact:true}).fill(username);await page.getByLabel('Senha',{exact:true}).fill(process.env.E2E_PASSWORD!);await page.getByRole('button',{name:'Entrar',exact:true}).click();await expect(page.getByRole('heading',{name:/^Empresas/})).toBeVisible();
}
async function select(page:Page,label:string,value:string){await page.getByLabel(label,{exact:true}).click();await page.locator('.ant-select-dropdown:visible').getByText(value,{exact:true}).click();await expect(page.locator('.ant-select-dropdown:visible')).toHaveCount(0);}
async function fill(page:Page,name:string,cnpj:string){await page.getByLabel('Razão social',{exact:true}).fill(name);await page.getByLabel('CNPJ',{exact:true}).fill(cnpj);await page.getByLabel('Inscrição municipal',{exact:true}).fill('000789');await select(page,'UF','CE');await select(page,'Município','Fortaleza');}
async function save(page:Page){await page.getByRole('button',{name:'Salvar empresa',exact:true}).click();await expect(page.getByRole('dialog',{name:'Cadastro de empresa'})).toBeHidden();}
test('empresas: criar com logo, refletir no seletor, editar e excluir',async({page})=>{
 await login(page);await expect(page.getByRole('cell',{name:'Empresa Beta',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'Nova empresa',exact:true}).click();await fill(page,'Empresa navegador',process.env.E2E_CNPJ!);
 await page.getByLabel('Logo da empresa',{exact:true}).setInputFiles(process.env.E2E_LOGO_PATH!);await save(page);
 let row=page.getByRole('row').filter({hasText:'Empresa navegador'});await expect(row).toBeVisible();
 await expect(page.getByLabel('Empresa ativa').locator('..')).toContainText('Empresa navegador');
 await row.getByRole('button',{name:'Editar',exact:true}).click();await expect(page.getByLabel('Razão social',{exact:true})).toHaveValue('Empresa navegador');
 await page.getByLabel('Razão social',{exact:true}).fill('Empresa atualizada');await save(page);
 row=page.getByRole('row').filter({hasText:'Empresa atualizada'});await expect(row).toBeVisible();
 await expect(page.getByLabel('Empresa ativa').locator('..')).toContainText('Empresa atualizada');
 await row.getByRole('button',{name:'Ver',exact:true}).click();await expect(page.getByRole('dialog',{name:'Detalhes da empresa'}).getByRole('img',{name:'Empresa atualizada',exact:true})).toBeVisible();await page.getByRole('button',{name:/^(Close|Fechar)$/}).click();
 await row.getByRole('button',{name:'Excluir',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Excluir',exact:true}).click();await expect(row).toHaveCount(0);
 await expect(page.getByLabel('Empresa ativa').locator('..')).toContainText('Empresa Alfa');
});
test('empresas: leitura não permite administrar',async({page})=>{await login(page,process.env.E2E_READER_USERNAME!);await expect(page.getByRole('button',{name:'Nova empresa',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Editar',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Excluir',exact:true})).toHaveCount(0);});
test('empresas: primeiro cadastro por usuário autorizado sem vínculo anterior',async({page})=>{await login(page,process.env.E2E_CREATOR_USERNAME!);await page.getByRole('button',{name:'Nova empresa',exact:true}).click();await fill(page,'Primeira empresa',process.env.E2E_CREATOR_CNPJ!);await save(page);await expect(page.getByLabel('Empresa ativa').locator('..')).toContainText('Primeira empresa');});
