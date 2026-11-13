import {test,expect,type Page} from '@playwright/test';
async function login(page:Page,reader=false){await page.goto('/clientes/app/ambiente-fiscal');await page.getByLabel('Usuário',{exact:true}).fill((reader?process.env.E2E_READER_USERNAME:process.env.E2E_USERNAME)!);await page.getByLabel('Senha',{exact:true}).fill(process.env.E2E_PASSWORD!);await page.getByRole('button',{name:'Entrar',exact:true}).click();await expect(page.getByRole('heading',{name:'Ambiente fiscal',exact:true})).toBeVisible();}
test('ambiente fiscal: certificado sintético privado, metadados e sequências',async({page})=>{
 await login(page);await expect(page.getByRole('cell',{name:'Ambiente Beta',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'Editar',exact:true}).click();
 await expect(page.getByLabel('Descrição',{exact:true})).toHaveValue('Ambiente Alfa');
 await expect(page.getByLabel('Senha do certificado',{exact:true})).toHaveValue('');
 await page.getByLabel('Descrição',{exact:true}).fill('Ambiente atualizado');
 await page.getByLabel('Certificado PKCS#12',{exact:true}).setInputFiles(process.env.E2E_CERTIFICATE_PATH!);
 await page.getByLabel('Senha do certificado',{exact:true}).fill('test-password');
 await page.getByRole('button',{name:'Salvar ambiente',exact:true}).click();
 await expect(page.getByRole('dialog',{name:'Configurar ambiente fiscal'})).toBeHidden();
 await expect(page.getByRole('cell',{name:'Ambiente atualizado',exact:true})).toBeVisible();
 await expect(page.getByRole('cell',{name:'Disponível',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Editar',exact:true}).click();
 await expect(page.getByLabel('Senha do certificado',{exact:true})).toHaveValue('');
 await page.getByRole('button',{name:/^(Close|Fechar)$/}).click();
 await page.getByRole('button',{name:'Ajustar sequências',exact:true}).click();
 await page.getByLabel('Último lote',{exact:true}).fill('30');await page.getByLabel('Último RPS',{exact:true}).fill('40');
 await page.getByRole('checkbox',{name:'Confirmo os números informados',exact:true}).check();
 await page.getByRole('button',{name:'Aplicar ajuste',exact:true}).click();
 await expect(page.getByRole('dialog',{name:'Ajustar sequências fiscais'})).toBeHidden();
 await expect(page.getByRole('cell',{name:'40',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Verificar prontidão',exact:true}).click();
 await expect(page.getByText(/Configuração pendente|Pré-requisitos locais disponíveis/)).toBeVisible();
});
test('ambiente fiscal: leitura não permite alteração nem exibe credenciais',async({page})=>{await login(page,true);await expect(page.getByRole('button',{name:'Editar',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Ajustar sequências',exact:true})).toHaveCount(0);await expect(page.getByText('test-password',{exact:true})).toHaveCount(0);});
