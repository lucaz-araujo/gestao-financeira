import {test,expect,type Page} from '@playwright/test';
async function login(page:Page,password=process.env.E2E_PASSWORD!){await page.getByLabel('Usuário',{exact:true}).fill(process.env.E2E_USERNAME!);await page.getByLabel('Senha',{exact:true}).fill(password);await page.getByRole('button',{name:'Entrar',exact:true}).click();await expect(page.getByRole('heading',{name:'Meu perfil',exact:true})).toBeVisible();}
test('usuário: perfil sem empresa e acesso legado pela sessão Django',async({page})=>{
 await page.goto('/clientes/app/perfil');await login(page);
 await expect(page.getByLabel('Nome',{exact:true})).toHaveValue('Pessoa');await page.getByLabel('Nome',{exact:true}).fill('Pessoa atualizada');await page.getByLabel('Linhas por página',{exact:true}).fill('25');
 await page.getByRole('button',{name:'Salvar perfil',exact:true}).click();await expect(page.getByText('Perfil atualizado.',{exact:true})).toBeVisible();
 const response=await page.request.get('/usuario/api/perfil/');expect(response.status()).toBe(200);expect((await response.json()).first_name).toBe('Pessoa atualizada');
 await page.reload();await expect(page.getByRole('heading',{name:'Meu perfil',exact:true})).toBeVisible();await expect(page.getByLabel('Nome',{exact:true})).toHaveValue('Pessoa atualizada');
});
test('usuário: alterar senha encerra acesso e permite entrar com nova credencial',async({page})=>{
 await page.goto('/clientes/app/perfil');await login(page);
 await page.getByLabel('Senha atual',{exact:true}).fill(process.env.E2E_PASSWORD!);await page.getByLabel('Nova senha',{exact:true}).fill(process.env.E2E_NEW_PASSWORD!);await page.getByLabel('Confirmar nova senha',{exact:true}).fill(process.env.E2E_NEW_PASSWORD!);
 await page.getByRole('button',{name:'Alterar senha',exact:true}).click();await expect(page.getByRole('heading',{name:'Entre no seu espaço',exact:true})).toBeVisible();await login(page,process.env.E2E_NEW_PASSWORD!);
 await page.getByRole('button',{name:'Sair',exact:true}).click();await expect(page.getByRole('heading',{name:'Entre no seu espaço',exact:true})).toBeVisible();
});
test('usuário: recuperar senha por e-mail local, usar link uma vez e entrar',async({page})=>{
 await page.goto('/clientes/app/perfil');await page.getByRole('link',{name:'Esqueci minha senha',exact:true}).click();
 await page.getByLabel('Usuário',{exact:true}).fill(process.env.E2E_USERNAME!);await page.getByLabel('E-mail',{exact:true}).fill(process.env.E2E_EMAIL!);await page.getByRole('button',{name:'Enviar instruções',exact:true}).click();
 await expect(page.getByText('Se os dados corresponderem a uma conta ativa, você receberá as instruções por e-mail.',{exact:true})).toBeVisible();
 const response=await page.request.get(process.env.E2E_MAIL_PATH!);const {link}=await response.json();const url=new URL(link);await page.goto(url.pathname+url.hash);
 await page.getByLabel('Nova senha',{exact:true}).fill(process.env.E2E_RESET_PASSWORD!);await page.getByLabel('Confirmar nova senha',{exact:true}).fill(process.env.E2E_RESET_PASSWORD!);await page.getByRole('button',{name:'Salvar nova senha',exact:true}).click();
 await expect(page.getByText('Senha alterada. Entre novamente.',{exact:true})).toBeVisible();expect(page.url()).not.toContain('#token=');
 await page.getByRole('link',{name:'Voltar para entrar',exact:true}).click();await login(page,process.env.E2E_RESET_PASSWORD!);
});

test('usuário: logout legado encerra sessão sem refresh React',async({page})=>{
 await page.goto('/clientes/app/perfil');await login(page,process.env.E2E_RESET_PASSWORD!);
 await page.context().clearCookies({name:'clientes_refresh'});
 await page.goto('/usuario/logout/');await expect(page.getByRole('button',{name:'Encerrar sessão',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Encerrar sessão',exact:true}).click();await expect(page.getByRole('heading',{name:'Entre no seu espaço',exact:true})).toBeVisible();
 expect((await page.request.get('/usuario/api/perfil/')).status()).toBe(401);
});
