import { test, expect, type Page } from '@playwright/test';
import { savePrintPreview } from './print-helpers';
async function login(page:Page,path='solicitacoes'){
 await page.goto('/clientes/app/compras-'+path);
 await page.getByLabel('Usuário',{exact:true}).fill(process.env.E2E_USERNAME!);
 await page.getByLabel('Senha',{exact:true}).fill(process.env.E2E_PASSWORD!);
 await page.getByRole('button',{name:'Entrar',exact:true}).click();
 await expect(page.getByRole('button',{name:'Novo cadastro',exact:true})).toBeVisible();
}
async function select(page:Page,label:string,value:string){
 await page.getByLabel(label,{exact:true}).click();
 await page.locator('.ant-select-dropdown:visible').getByText(value,{exact:false}).click();
 await expect(page.locator('.ant-select-dropdown:visible')).toHaveCount(0);
}
async function save(page:Page){await page.getByRole('button',{name:'Salvar cadastro',exact:true}).click();await expect(page.locator('.ant-drawer:visible')).toHaveCount(0);}
async function confirm(page:Page,button:string,confirm=button){await page.getByRole('button',{name:button,exact:true}).click();await page.locator('.ant-popover:visible').getByRole('button',{name:confirm,exact:true}).click();}
test('compras: solicitação, orçamento, autorização e finalização',async({page})=>{
 await login(page);
 await page.getByRole('button',{name:'Novo cadastro',exact:true}).click();
 await page.getByLabel('Descrição',{exact:true}).fill('Compra E2E');
 await select(page,'Item de compra','Papel');
 await page.getByLabel('Quantidade',{exact:true}).fill('2,500');
 await page.getByLabel('Valor unitário',{exact:true}).fill('10');
 await save(page);await expect(page.getByText('Compra E2E',{exact:true})).toBeVisible();
 await page.getByRole('link',{name:'Orçamentos de compra',exact:true}).click();
 await page.getByRole('button',{name:'Novo cadastro',exact:true}).click();
 await select(page,'Solicitação','Compra E2E');await select(page,'Fornecedor','Fornecedor Alfa');
 await select(page,'Item de compra','Papel');
 await page.getByLabel('Quantidade',{exact:true}).fill('2,500');
 await page.getByLabel('Valor unitário',{exact:true}).fill('5');
 await save(page);await expect(page.getByRole('cell',{name:'Fornecedor Alfa',exact:true})).toBeVisible();
 await page.getByRole('link',{name:'Solicitações de compra',exact:true}).click();
 await expect(page.getByRole('cell',{name:'Em cotação',exact:true})).toBeVisible();
 await confirm(page,'Autorizar');await expect(page.getByRole('cell',{name:'Autorizada',exact:true})).toBeVisible();
 await confirm(page,'Finalizar');await expect(page.getByRole('cell',{name:'Finalizada',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Comparativo',exact:true}).click();
 await expect(page.getByRole('button',{name:'Imprimir comparativo',exact:false})).toBeVisible();
 await expect(page.getByText('Selecionado',{exact:true})).toBeVisible();
 await page.evaluate(() => { window.print = () => {}; });
 await page.getByRole('button',{name:'Imprimir comparativo',exact:true}).click();
 await savePrintPreview(page,'comparativo-compras');
});
test('compras: fornecedor e dados bancários como texto',async({page})=>{
 await login(page,'fornecedores');await page.getByRole('button',{name:'Novo cadastro',exact:true}).click();
 for(const [label,value] of [['Instituição','Fornecedor navegador'],['Endereço','Rua A'],['Número','1'],['Bairro','Centro'],['CEP','60000000'],['Agência','0001'],['Conta bancária','0000123']])await page.getByLabel(label,{exact:true}).fill(value);
 await save(page);
 const row=page.getByRole('row').filter({hasText:'Fornecedor navegador'});await expect(row).toBeVisible();
 await row.getByRole('button',{name:'Ver',exact:true}).click();await expect(page.getByText('0000123',{exact:true})).toBeVisible();
});
