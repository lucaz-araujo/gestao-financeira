# Clientes e Produtos — React 19, TypeScript e Ant Design

Acesso integrado: **`/clientes/app/`**, na mesma origem do Django. O menu do sistema anterior já aponta para as telas novas.

## Desenvolvimento

Use Node 26 (o projeto contém `.nvmrc`). Na raiz do repositório:

```bash
source ~/.nvm/nvm.sh
nvm use
npm ci
npm run dev
```

Em outro terminal, inicie Django normalmente com o ambiente Python do projeto:

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Acesse `http://127.0.0.1:5173/clientes/app/`. O Vite encaminha as chamadas `/clientes/api/` e `/produtos/api/` para Django; o navegador usa uma única origem, sem liberar CORS. Não publique o servidor de desenvolvimento.

## Build e execução integrada

```bash
npm run build
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
```

O build é gerado em `static/clientes-app/`, fora do Git. Django lê o manifest Vite, incluindo o CSS dos chunks importados, e serve a página HTML em `/clientes/app/` e suas subrotas. Em produção, o servidor estático deve servir `/static/` a partir de `STATIC_ROOT`. Configure HTTPS e `CLIENTES_AUTH_COOKIE_SECURE=True` (padrão quando DEBUG=False). A conexão administrativa é utilizada apenas para migrations, não para o processo web. Reinicie os processos Django ao alterar configurações.

## Funcionalidades

- Login com usuário/senha Django; logout com revogação do refresh.
- Seleção entre empresas vinculadas à conta; troca de empresa remonta as telas e descarta dados/formulários anteriores.
- Clientes e parceiros: consulta paginada, busca, detalhes, criação, edição e exclusão protegida por vínculos.
- Clientes: dados pessoais, responsável, endereço, integrações, senha TCM somente escrita, dados bancários e acessos.
- Liberações: criação por competência/ano, consulta/cópia de chave, regeneração e exclusão.
- Bloqueios: períodos, indicadores de acesso, edição e exclusão.
- Relatórios de clientes, parceiros, produtos, contratos e aniversariantes. Carregam todas as páginas antes da exportação CSV ou impressão; a tabela informa o número de linhas exportáveis.
- Estados de carregamento, ausência de dados, falta de permissões e falhas de rede; erros da API mapeados para os campos Ant Design.
- Navegação e formulários adaptados para dispositivos móveis.

Botões e navegação usam as permissões recebidas da API. A autorização permanece obrigatória no backend. Grupos precisam das permissões dos modelos de clientes/parceiros/bloqueios e de `financeiro.add_recreceita` para listar/criar liberações. Usuários sem empresas/permissões recebem uma orientação na tela.

## Contrato de autenticação

Prefixo `/clientes/api/auth/`:

- `GET csrf/`: fornece token CSRF e cookie de proteção.
- `POST login/`: recebe username/password; devolve access token. Tentativas limitadas a 10/minuto por IP no cache configurado.
- `POST refresh/`: lê o refresh do cookie, devolve novo access e rotaciona o refresh; token anterior vai para a blacklist.
- `POST logout/`: revoga o refresh e limpa o cookie.
- `GET me/`: recebe Bearer access e devolve usuário, permissões e empresas autorizadas.

O access token fica apenas em memória. Refresh em cookie HttpOnly, SameSite=Lax, restrito ao caminho de autenticação. Escritas com cookie exigem CSRF, inclusive login e logout. O refresh nunca é devolvido no corpo da resposta. O único valor salvo em sessionStorage é a preferência de empresa; o backend verifica esse ID a cada requisição.

O cliente HTTP renova uma única vez quando recebe 401, compartilhando a renovação entre requisições simultâneas da mesma aba. Refresh inválido encerra a sessão; 403 não provoca refresh; falhas de rede/5xx não encerram a sessão automaticamente. A página tenta restaurar a sessão por refresh ao abrir/recarregar. O access já emitido permanece válido por até 5 minutos após o logout; o refresh é revogado imediatamente. As rotas antigas `/api/token/` continuam disponíveis para os consumidores existentes, compartilhando a configuração de rotação.

Em instalações com vários processos, configurar um cache compartilhado para tornar o limite de tentativas consistente entre workers e proteção complementar no proxy. Agendar `manage.py flushexpiredtokens` diariamente. Renovações simultâneas entre abas diferentes não compartilham o mesmo bloqueio em memória.

## Testes

```bash
npm test
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py test clientes.tests financeiro.test_postgresql \
  --settings=financeiro.pg_test_settings --keepdb
```

Navegador real contra Django/PostgreSQL descartável (compilar antes):

```bash
npm run build
PLAYWRIGHT_BROWSERS_PATH=/tmp/gestao-playwright npx playwright install chromium
PATH="$PWD/node_modules/.bin:$PATH" DATABASE_USE_ADMIN=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/gestao-playwright \
  .venv/bin/python manage.py test clientes.browser_tests --settings=financeiro.pg_test_settings --keepdb
```

O Node ativo precisa ser 26. A fixture cria usuário/empresas sintéticos no banco de testes; nenhuma senha real é usada. Screenshots ficam em `/tmp/gestao-clientes-e2e`; traces de falhas em `test-results/`.


## App Produtos

A tela fica em `/clientes/app/produtos`, no mesmo frontend autenticado. `/produtos/app/` redireciona para ela e a navegação React abre essa tela. A navegação aparece para quem possui `produtos.view_produto`; criação, alteração e exclusão exigem, respectivamente, `produtos.add_produto`, `produtos.change_produto` e `produtos.delete_produto`.

API: `/produtos/api/produtos/` (GET paginado/POST) e `/produtos/api/produtos/{id}/` (GET/PUT/PATCH/DELETE). Usa Bearer JWT ou sessão com CSRF e a mesma seleção de empresa (`X-Empresa-ID`, parâmetro `empresa`, ou sessão). A empresa deve estar vinculada ao usuário; IDs de outras empresas retornam 404. A UF do usuário não filtra produtos, pois eles pertencem à empresa e não a um município.

Campos graváveis: `descricao` (até 60 caracteres), `sigla` (até 5), `tipo_produto` (`P` ou `S`) e `valor`. Descrição, sigla e valor são obrigatórios. Valor aceita zero, não aceita negativos e comporta até 8 dígitos inteiros e 2 decimais; enviar decimal como string (`"1234.56"`). O frontend usa apresentação em reais e entrada com vírgula. `id` e `empresa` são somente leitura. Não foram introduzidas restrições de unicidade sobre o catálogo existente.

Filtros: `search` procura descrição ou sigla; `tipo_produto=P|S` seleciona o tipo. Paginação `page`/`page_size`, padrão 50, máximo 200. Ordenação por descrição e ID. Exclusão com contrato ou liberação vinculada retorna 409 e preserva os dependentes. Valores inválidos retornam 400 com erros por campo. Cadastros antigos com valor/sigla nulos continuam consultáveis, mas precisam ser completados ao serem editados.

`produtos/forms.py` e os cinco templates antigos foram removidos. Os modelos não precisaram de alteração no schema nem migration; o método `clean()` e o serializer validam os dados. As rotas antigas mantêm os nomes de `reverse()`, respondem JSON e aceitam POST legado em edição/exclusão, exigindo a permissão da ação correta.

Testes de API e navegador:

```bash
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py test produtos.tests clientes.tests financeiro.test_postgresql \
  --settings=financeiro.pg_test_settings --keepdb
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py test produtos.browser_tests clientes.browser_tests \
  --settings=financeiro.pg_test_settings --keepdb
```

As fixtures de cada app selecionam seu próprio arquivo Playwright. Dados e usuários de teste são criados exclusivamente no banco isolado. Screenshots de Produtos ficam em `/tmp/gestao-produtos-e2e`.


## App Contratos

Tela `/clientes/app/contratos`, atalho `/contratos/app/`. Compartilha autenticação, empresa e tema. Exige `contratos.view_contrato` para consultar, `add_contrato` para criar, `change_contrato` para editar e `delete_contrato` para excluir. Itens e renovações pertencem ao agregado contrato: seguem a permissão do contrato e não têm endpoints independentes de escrita.

API `/contratos/api/contratos/` e `/contratos/api/contratos/{id}/`: CRUD JSON paginado com JWT ou sessão/CSRF. Filtros `search` (número/cliente), `cliente`, `parceiro`, `uf`, `ativo` e `dt_inicial`/`dt_final` (intervalo inclusivo de vencimento do contrato, ambas as datas obrigatórias quando utilizado). IDs de filtros aceitam valores repetidos ou separados por vírgula. Empresa e UF do usuário são conferidas no servidor; cliente e contrato precisam pertencer à empresa selecionada.

A resposta de lista contém o resumo. GET por ID inclui `itens`, `renovacoes` e o resumo das `notas` vinculadas. Em POST/PATCH/PUT:

- Campos principais: cliente, número (20 caracteres), dia da nota (1–31), exercício, datas inicial/final, objeto, observações e indicadores ativo/emitir nota/serviço no município.
- Financeiro: valor bruto, percentuais ISS/IRPJ, valores ISS/IRPJ e valor líquido, com duas casas decimais. Não negativos; percentuais entre 0 e 100. Valores informados são preservados e não são automaticamente substituídos pela soma dos itens nem por um cálculo de impostos.
- `itens`: lista de `{id?, produtos, valor}`. Produto da mesma empresa e valor não negativo com até cinco casas decimais (limite 7 dígitos inteiros).
- `renovacoes`: lista de `{id?, dt_data_inicio, dt_data_final}`. Fim igual/posterior ao início. As renovações são registros de histórico: não alteram automaticamente a data final principal, comportamento preservado do legado.
- Omitir uma lista em PATCH preserva seus registros; enviar uma lista substitui o conjunto correspondente. IDs mantêm registros existentes; linhas sem ID são novas; linhas omitidas de uma lista enviada são removidas. Lista vazia remove todos os filhos desse tipo. IDs de outro contrato ou repetidos são rejeitados. Cada linha enviada deve conter todos os campos graváveis, inclusive em PATCH. Limite de 200 linhas por lista.

Pai e filhos são validados antes de gravar, e toda a gravação acontece em uma transação. Edição e exclusão bloqueiam a linha do contrato para serializar operações concorrentes. A exclusão sem notas remove apenas os próprios itens/renovações e o contrato; preserva clientes e produtos. Qualquer nota vinculada impede a exclusão (409), inclusive notas canceladas ou registros inconsistentes de empresa. Não é permitido trocar o cliente se houver notas; editar valores não reescreve documentos fiscais já emitidos. Não há criação, cancelamento ou baixa de nota por esta tela.

`POST calcular/` recebe valor_bruto, perc_iss e perc_irpj e devolve valor_iss, valor_irpj e valor_liquido. Usa Decimal, arredondamento HALF_UP a duas casas decimais e rejeita percentuais somados acima de 100. É uma prévia, não grava nada. O botão “Calcular pelos percentuais” é explícito; a gravação normal preserva valores financeiros manuais.

`GET opcoes/?tipo=clientes|parceiros|produtos` devolve IDs/rótulos da empresa, paginados e pesquisáveis (`search` ou `id`). É acessível a operadores autorizados do contrato sem exigir permissão de edição nos outros apps.

`GET relatorio/?tipo_relatorio=S|C` recebe os mesmos filtros e retorna os dados paginados e `valor_total` líquido do conjunto filtrado completo. O frontend carrega todas as páginas para exportar CSV/imprimir. Tipos no seletor: Contratos — simplificado e Contratos e produtos. O total não é multiplicado pelo número de itens.

A impressão individual apresenta um resumo com dados principais, financeiro, itens, renovações e notas. É possível salvar em PDF pelo navegador; não gera um novo instrumento jurídico nem usa o gerador antigo, que retornava None. A rota nomeada `print_contrato` direciona ao resumo específico no React. Os outros nomes de rotas legadas continuam disponíveis, respondendo JSON, inclusive POST legado para editar/excluir com a permissão da ação correta.

`contratos/forms.py` e os nove templates antigos foram removidos. As alterações dos modelos são métodos de validação; não alteram o schema nem recalculam registros históricos. O utilitário legado de valores por extenso permanece no repositório sem uso pelo novo fluxo.

Testes:

```bash
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py test contratos.tests produtos.tests clientes.tests financeiro.test_postgresql \
  --settings=financeiro.pg_test_settings --keepdb
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py test contratos.browser_tests produtos.browser_tests clientes.browser_tests \
  --settings=financeiro.pg_test_settings --keepdb
```

Screenshots de Contratos: `/tmp/gestao-contratos-e2e`. Fixtures usam empresas/usuários sintéticos no banco PostgreSQL isolado.

## App Notas fiscais

Tela `/clientes/app/notas`, atalho `/notas/app/`, API `/notas/api/notas/`. Usa os dados do PostgreSQL, JWT ou sessão com CSRF, empresa vinculada ao usuário e escopo de UF do cliente. Permissões: `notas.view_nota` para consulta/relatórios/histórico/consulta de lote; `add_nota` para rascunhos/geração por contratos; `change_nota` para edição, emissão, consulta individual, cancelamento e e-mails; `delete_nota` para excluir rascunhos; `financeiro.add_docreceita` para gerar receita. Nenhuma transmissão ou envio ocorre por GET. No admin, notas e operações fiscais são somente leitura; as alterações passam pelos fluxos da API.

O `NotaSerializer` é um ModelSerializer. Empresa, sequências RPS/lote, protocolos, autorização, cancelamento e indicadores de envio são somente leitura. Dinheiro usa string decimal com duas casas; alíquota de 0 a 100. Exercício aceita anos atuais, sem a antiga limitação até 2021. A API mantém validação de segurança e integridade, além da validação de apresentação no React. Edição/exclusão permitidas apenas em rascunhos sem financeiro, pagamento ou histórico de operações.

`POST gerar/` recebe `{contratos: [ids], competencia: 1..12, exercicio: ano, decimo_terceiro: false}`. Cria rascunhos em uma transação, bloqueando contratos em ordem; repetir a mesma competência/seleção preserva a nota e seus valores. Geração com décimo terceiro duplica o bruto uma única vez. Mantida a regra legada de valor líquido igual ao bruto na geração e de receita pelo bruto; ISS é destacado separadamente. Alterações manuais dos valores não são recalculadas ao salvar. O XML usa o valor líquido e ISS gravados na nota. Revisão tributária das regras do município continua necessária antes de operar em produção.

`GET configuracao/` informa ambiente (homologação/produção), disponibilidade fiscal, pendências e disponibilidade de e-mail. Dependências, assinador XMLSec, dados do emissor, certificado PKCS#12 e validade são verificados. `GET opcoes/` pesquisa contratos; `opcoes/?tipo=clientes` pesquisa clientes do mesmo escopo. Filtros de lista/relatório: `search`, `cliente`, `contrato`, `uf`, `competencia`, `exercicio`, `estado`, `email_enviado`, `pagas` e intervalo inclusivo `dt_inicial`/`dt_final`. Datas usam emissão; quando `pagas=true`, pagamento. Relatório inclui total líquido e ISS de todo o conjunto filtrado, independentemente da paginação.

Ações por nota, todas POST: `emitir/`, `consultar/`, `consultar_lote/`, `cancelar/`, `email/`, `email_cliente/`, `financeiro/`. As seis primeiras exigem `{confirmar: true}`, com `justificativa` obrigatória no cancelamento, registrada na auditoria interna (o protocolo legado não transmite esse texto). Envie `Idempotency-Key` UUID para repetir uma requisição sem repetir a operação. A API reserva RPS/lote sob bloqueio de empresa e registra a operação antes da chamada externa, sem manter transação de banco aberta durante a rede. Protocolo de envio não equivale a autorização; código de verificação e número são gravados somente com resposta correspondente à nota/RPS. Cancelamento depende de confirmação explícita do provedor.

`historico/` é paginado e registra usuário, ação, horário e resultado. Resposta perdida, timeout ou falha local após transmissão pode ter resultado externo incerto: HTTP 502 e estado `incerta`. Não há reenvio automático; novas operações de escrita são bloqueadas até conciliação. Consulte por protocolo, número ou RPS reservado para confirmar emissão. Consulta confirmada concilia emissão/cancelamento anteriores; cancelamento exige `Sucesso=true` e identificação da nota, além da presença de uma confirmação. Situação de lote isolada não confirma autorização. Notas legadas com RPS/lote reservado e sem histórico de emissão ou resultado fiscal ficam em estado incerto e exigem consulta; não podem ser editadas, excluídas ou reenviadas. Número informado manualmente serve para consulta e impede nova emissão enquanto estiver preenchido. E-mail incerto exige conferência no servidor de e-mail; não é liberado automaticamente por uma consulta fiscal. Operações que ficaram `executando` após interrupção do processo também exigem conciliação administrativa antes de qualquer nova tentativa. Preserve o histórico na reconciliação.

`financeiro/` devolve a receita existente sem redefinir valor recebido, vencimento ou situação, e não duplica documentos. Apenas notas autorizadas, sem cancelamento ou operação incerta/pendente podem gerar receita. Cancelamento fiscal é bloqueado quando há financeiro/pagamento: não estorna recebimentos nem exclui receitas.

`link_publico/` cria um link assinado com validade de sete dias; documentos públicos não expõem rascunhos nem notas de outros clientes/empresas. Links antigos baseados em identificadores previsíveis foram desativados (410). A impressão identifica rascunhos sem validade fiscal; documentos autorizados mostram código de verificação. É uma representação para consulta, cuja autenticidade deve ser conferida no município.

`notas/forms.py` e os 14 templates antigos foram removidos. Três templates são necessários fora da SPA: `nota_email.html` para e-mails, `nota_publica.html` para consulta/impressão pública e `notas_cliente_publicas.html` para relação pública. O campo legado de PDF e arquivos existentes foram preservados.

E-mail usa Django EmailBackend, com `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`/`EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL` e `PUBLIC_APP_URL` HTTPS configurados por ambiente. Configure apenas um entre TLS e SSL. Nenhuma senha de SMTP fica no código. Aceite pelo servidor SMTP não confirma entrega ao cliente. A senha anteriormente presente no código legado deve ser rotacionada pelo responsável da conta e removida do histórico antes de compartilhar o repositório; a aplicação não tem autorização para trocar credenciais externas.

O adaptador usa configuração/certificado da empresa da nota, entidades por requisição e arquivos temporários isolados. Extração PKCS#12 usa cryptography; assinatura identifica a chave explicitamente para XMLSec 1.3 e mantém o lote na posição final antes de assinar, sem mover a assinatura depois; HTTPS usa SSLContext compatível com Python atual e remove os PEM temporários ao terminar. Consulta por número/RPS segue os XSDs locais, que não admitem Signature; consulta de lote mantém assinatura e não modifica o XML após assinar. Cancelamento mantém o formato específico do método legado Speedgov v2, diferente do XSD v1 local; seu aceite precisa ser confirmado em homologação. Os bindings Speedgov foram regenerados com PyXB-X a partir dos XSDs locais: `.venv/bin/python scripts/regenerate_speedgov.py`. Não edite manualmente os bindings gerados.

Validação:

```bash
npm run build
npm test
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py test notas.tests contratos.tests produtos.tests clientes.tests financeiro.test_postgresql \
  --settings=financeiro.pg_test_settings --keepdb
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py test notas.browser_tests \
  --settings=financeiro.pg_test_settings --keepdb
```

Testes usam PostgreSQL isolado e dados sintéticos. Teste do adaptador gera certificado sintético, serializa XMLs e verifica assinatura e schema local, com transporte simulado. Navegador exercita rascunhos, geração, autorização/cancelamento simulados, e-mail em memória, receita, relatório, impressão, empresa e permissões. Screenshots em `/tmp/gestao-notas-e2e`. Não houve emissão, cancelamento ou e-mail reais. O ambiente local está configurado para produção, mas o certificado não está disponível; emissão real permanece pendente de certificado válido e homologação com o provedor. E-mail depende da configuração SMTP e URL pública.

## App Contas

Telas: `/clientes/app/bancos`, `/clientes/app/contas`, `/clientes/app/movimentos` e `/clientes/app/transferencias`. Atalho `/conta/app/`. A navegação React direciona às telas do módulo e tem rolagem para acomodar todos os módulos. Dados vêm do PostgreSQL; nenhuma transferência bancária externa é executada por este app.

API `/conta/api/` com `bancos/`, `contas/`, `movimentos/` e `transferencias/`: CRUD JSON paginado, JWT ou sessão/CSRF. A empresa precisa estar vinculada ao usuário (`X-Empresa-ID`, parâmetro `empresa` ou sessão). Permissões seguem cada modelo: `conta.view_*`, `add_*`, `change_*`, `delete_*`. O app não possui escopo de UF, pois contas e movimentos pertencem à empresa. Bancos são catálogo global, como no modelo existente: mudanças autorizadas nesse catálogo afetam todas as empresas. Contas, plano de contas, movimentos e transferências são limitados à empresa selecionada.

Os quatro serializers são ModelSerializer. Empresa e responsável pelo movimento são definidos no servidor. Banco mantém código até 8 caracteres e nome até 10. Conta preserva agência/número/dígitos como texto, incluindo zeros à esquerda, e valida plano contábil da mesma empresa. A API verifica duplicidade de código/nome de banco e combinação bancária na mesma empresa; não foram adicionadas constraints de unicidade aos cadastros históricos. Valores de movimentos/transferências são positivos, com até 12 dígitos inteiros e três casas decimais, enviados como strings. A interface também mostra três casas decimais. Campos financeiros não são calculados com float.

`GET opcoes/?tipo=bancos|contas|planos` pesquisa IDs/rótulos paginados (`search`, `id`). Operadores de movimentos/transferências podem escolher contas sem possuir permissão para alterá-las. Exclusão de banco ou conta com vínculos retorna 409 e preserva os dependentes. Admin do Django ficou somente leitura para os quatro modelos; operações passam pela API.

Movimentos manuais aceitam TED, DOC, CHE, TAR, OUT e DEP; direção C ou D. TRA é reservado ao fluxo de transferência. Vínculos `receita`, `despesa` e `transferencia` são somente leitura; movimentos vinculados não podem ser alterados ou excluídos isoladamente. A resposta informa `editavel` para orientar a interface. Alterações/exclusões manuais verificam o período original e o período/conta de destino, impedindo deslocar um lançamento de caixa já fechado para uma data aberta.

Transferências exigem contas diferentes da mesma empresa. Criação, edição e exclusão do registro e de seus dois movimentos acontecem na mesma transação. Edição identifica os movimentos pela FK da transferência e direção, nunca pelo número do documento. São bloqueadas as contas envolvidas, em ordem de ID, e verificadas origem e destino, tanto no período antigo quanto no novo. O bloqueio usa as mesmas linhas de conta que a função PostgreSQL de fechamento. Uma falha no segundo movimento reverte pai e primeiro movimento. Exclusão em período aberto remove os dois movimentos e o registro, preservando a auditoria; não é uma ordem de estorno no banco.

Transferências legadas com par ausente, duplicado ou incompatível ficam sinalizadas como “Conciliação necessária”; não são automaticamente reparadas nem permitem edição/exclusão. `GET transferencias/?integridade=pendente|consistente` e o filtro da tela permitem localizar esses registros. A auditoria local encontrou 105 transferências nessa condição, em 1.897 registros, sem empresas divergentes nos vínculos das contas. Contagens de referência: 7 bancos, 13 contas, 41.959 movimentos e 2.295 fechamentos. Nenhum registro financeiro existente foi alterado na migração.

Auditoria de leitura, com CSV opcional criado com permissão 0600, sem sobrescrever um arquivo existente:

```bash
.venv/bin/python manage.py auditar_transferencias
.venv/bin/python manage.py auditar_transferencias --output .backups/transferencias_para_conciliacao.csv
```

O CSV indica ID da transferência, empresa, data, contas, valor, quantidade e totais dos movimentos. A decisão sobre cancelamento histórico, recomposição ou ajuste depende de conferência dos documentos e extratos originais; a quantidade de movimentos isolada não determina qual correção seria correta.

Relatórios próprios da tela: movimentações, cheques emitidos (CHE/D), extrato por conta e transferências. Carregam todas as páginas antes de exportar CSV ou imprimir, com proteção contra fórmulas nas células de texto. `movimentos/relatorio/` retorna créditos, débitos e resultado do conjunto filtrado completo; `transferencias/relatorio/` retorna total transferido, contado uma vez por transferência. Filtros: `search`, par `dt_inicial`/`dt_final`, `conta` para movimentos, `conta_origem`/`conta_destino` e `integridade` para transferências; movimentos também aceitam `tipo_movimento` e `tipo_documento`.

`GET movimentos/extrato/?conta=ID&dt_inicial=AAAA-MM-DD&dt_final=AAAA-MM-DD` exige conta e intervalo. Usa o último fechamento anterior ao início, soma os movimentos ocorridos depois dele e antes do início e acrescenta o resultado do intervalo. Na ausência de fechamento anterior, soma o histórico de movimentos anterior ao início. Não exige fechamento exatamente na véspera. Retorna `saldo_anterior`, créditos, débitos, `saldo_periodo` e `saldo_final`. O extrato usa todos os lançamentos da conta no intervalo; filtros de texto/tipo não recortam seu saldo. A aritmética preserva as quatro casas existentes no fechamento; apresentação monetária da tela usa três casas, conforme os movimentos.

Compatibilidade com Financeiro: `AddMovimento` continua disponível, mas sincroniza pelo ID do recebimento/pagamento, evitando sobrescrever outro movimento com o mesmo número/data. Valida conta, empresa e fechamento. Os dois salvamentos legados de baixa foram envolvidos em transação com validação de empresa e erro de formulário; importação de baixas usa transação por item e informa falhas. Assim, uma falha ao gerar o movimento reverte a baixa correspondente. Recebimentos/pagamentos e o restante do Financeiro continuam nos fluxos legados, pendentes de sua própria migração; não foram reescritos seus cálculos ou regras de quitação.

`conta/forms.py` e os dez templates deste app foram removidos após verificar ausência de referências externas. Validação de segurança e integridade permanece nos models, serializers e serviços, além da apresentação no React. As alterações dos models não alteram o schema; nenhuma migration ou recalculação de dados foi necessária. Nomes de rotas legadas foram preservados para reverse; listas/relatórios direcionam ao React, escrita exige métodos HTTP próprios da API. O antigo endpoint sem ID de estorno direciona à tela, onde a exclusão do registro específico exige confirmação.

Testes:

```bash
npm run build
npm test
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py test conta.tests notas.tests contratos.tests produtos.tests clientes.tests financeiro.test_postgresql \
  --settings=financeiro.pg_test_settings --keepdb
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py test conta.browser_tests \
  --settings=financeiro.pg_test_settings --keepdb
```

Fixtures usam exclusivamente banco PostgreSQL isolado e dados sintéticos. Testes cobrem empresas/permissões/CSRF, pares de transferência, rollback de falhas, vínculos protegidos, caixa fechado dos dois lados e períodos antigo/novo, extrato com intervalo entre fechamento e início, relatórios, compatibilidade das baixas legadas e auditoria de leitura. Screenshots em `/tmp/gestao-contas-e2e`.

## Financeiro — React e DRF

Rotas React: `/clientes/app/receitas`, `/clientes/app/despesas`, `/clientes/app/fechamentos`.
API `/financeiro/api/`: `receitas`, `despesas`, `fechamentos`, `opcoes`. Os documentos expõem saldo e total baixado calculados pelos registros de baixa, independentemente do cache legado. `baixas` lista o histórico; `baixar` exige UUID `idempotencia`; `estornar` exige ID de uma baixa específica. A migration 0031 guarda as chaves mesmo após estorno, impedindo recriação acidental por repetição da requisição. Baixas, movimento e atualização do documento confirmam juntos em transação, respeitando fechamento e empresa. Receitas também respeitam UF do usuário.

Recebimentos parciais permanecem abertos. A data de pagamento da nota e a liberação de competência são atualizadas somente após quitação dos documentos da nota. Estornos preservam liberações de acesso existentes, inclusive manuais; revisar acesso é uma ação administrativa independente. Documentos com baixas não podem ser editados ou excluídos antes da conciliação/estorno. A duplicação de despesas cria até 60 cópias mensais, com ajuste para último dia do mês. Fechamentos são calculados no PostgreSQL e somente o último de cada conta pode ser reaberto. Valores de documentos têm duas casas; fechamentos preservam quatro.

Conciliação: `receitas/previsualizar/` aceita CSV delimitado por `;` com colunas `data;valor;documento;historico` (DD/MM/AAAA, 1.234,56) ou TXT BB no formato posicional legado, até 2 MB/200 créditos. A prévia não grava; cada linha recebe assinatura vinculada ao usuário e empresa, válida por 30 minutos. `receitas/conciliar/` exige conta e vínculos escolhidos; confirma o lote inteiro ou reverte tudo, com chave estável por arquivo/linha. Só importe créditos efetivamente conferidos. Formatos TXT distintos devem ser convertidos para o CSV documentado.

Relatórios filtram vencimento, situação e busca; a API aceita também datas de pagamento e vínculos. Totais abrangem todo o filtro; CSV exporta todas as páginas e neutraliza fórmulas. A análise consolidada exige acesso a receitas/despesas e usuário sem restrição de UF. O admin financeiro é de leitura para impedir bypass dos serviços. `financeiro/forms.py` e os 31 templates antigos foram removidos; URLs antigas conduzem à revisão no React e preservam os nomes usados pelo sistema.

Auditoria local em 04/11/2026: 15.041 recebimentos e 651 pagamentos sem exatamente um movimento vinculado. Isso identifica ausência/duplicação, não comprova saldo correto dos demais. Registros históricos foram preservados. Operações sobre esses vínculos são bloqueadas até conciliação documental; não foi executada correção automática. Backup anterior à migration em `.backups/antes_financeiro_20261104T161539Z.dump` (privado).

Validação: `financeiro.tests` cobre quitação parcial, estorno individual, idempotência, falhas/rollback, fechamento, isolamento, CSV assinado e lote atômico. `financeiro.browser_tests` verifica fluxos reais do React usando dados sintéticos em banco de testes separado.

## Contábil — React e DRF

Rotas `/clientes/app/contabil-planos`, `contabil-centros`, `contabil-tipos` e `contabil-lancamentos`. API `/contabil/api/{planos,centros,tipos,lancamentos}/`, com JWT/sessão, CSRF para sessão, permissão de modelo por ação e empresa obrigatória. Busca e paginação; CRUD em drawers React. O admin dos cadastros migrados é de consulta.

Planos e centros são limitados à empresa. Tipos sem plano são um catálogo compartilhado legado de consulta: novos tipos exigem um plano da empresa; o vínculo de tipos existentes não pode ser trocado. Alterações de tipos com despesas/solicitações de outras empresas são bloqueadas. Códigos duplicados são validados no contexto da empresa, com bloqueio transacional do cadastro da empresa. Lançamentos exigem planos distintos da mesma empresa, data/hora, tipo e valor positivo com duas casas. São registros contábeis independentes; não geram movimentos bancários automaticamente.

`contabil/forms.py` e quatro templates antigos removidos; URLs antigas preservam nomes de reverse e direcionam listas ao React. Models receberam validações sem mudança de schema. Nenhuma migration ou reclassificação histórica foi necessária. Histórico sem interface prévia (`Historico`) permanece no modelo, sem novo fluxo.

Auditoria local: 236 planos e três centros, todos com empresa; 96 tipos compartilhados sem plano; nenhum lançamento com contas ausentes ou empresas distintas. Registros preservados. Validação: seis testes de API e cenário Playwright de cadastro/edição/exclusão de plano e proteção do catálogo compartilhado, junto à regressão de Financeiro/Contas.

## Compras — React e DRF

Rotas React `/clientes/app/compras-{fornecedores,unidades,itens,solicitacoes,orcamentos}`. API `/compras/api/{fornecedores,unidades,itens,solicitacoes,orcamentos,opcoes}/`, com JWT/sessão, CSRF de sessão, permissões de modelo por ação e empresa obrigatória. Solicitantes consultam suas próprias solicitações/orçamentos; responsáveis com `compras.autorizar_solicitacao` ou `compras.finalizar_solicitacao` consultam os da empresa. Essas duas permissões da migration 0018 devem ser atribuídas aos responsáveis pelo administrador; nenhuma concessão automática a usuários existentes.

Solicitação e orçamento usam listas `linhas` aninhadas com `item`, `quantidade`, `valor`. A API calcula `valor_total` e o total da solicitação usando Decimal, arredondamento HALF_UP com três casas; rejeita duplicatas, quantidades não positivas, valores negativos, totais acima de 9.999.999,999 e mais de 100 linhas. Empresa, solicitante, autorizador, total, status e seleção de melhor preço não são controlados pelos campos de formulário. Catálogos de itens/unidades e relações com centros/tipos de despesa respeitam a empresa. CPF/CNPJ, e-mail e município/UF dos fornecedores são validados; dados bancários permanecem texto. O nome do fornecedor conserva a unicidade global do schema legado.

Fluxo: AB → PE (início da cotação); PE → AU (autorização específica, com cotação válida de todos os itens); AU → FI (finalização específica). AB/PE/AU podem ir para CA. FI/CA são terminais. O primeiro orçamento também leva AB para PE. Itens/cabeçalho da solicitação só mudam em AB e sem orçamento; orçamentos só mudam em PE. Cada linha cotada exige o item e a quantidade exatos da solicitação. Autorização congela cotações. Finalização escolhe o menor valor unitário por item exclusivamente nos orçamentos da solicitação e empresa, com empate por data mais antiga e depois ID. Atualiza o vínculo correto com OrcamentoItens e persiste totais; repetição da finalização em FI é idempotente. Não cria despesa financeira nem executa compra externa. Comparativo e impressão disponíveis no React.

Escritas aninhadas e transições são atômicas; bloqueio da solicitação serializa alterações de orçamentos, autorização e finalização. Excluir registros vinculados resulta em 409. O admin migrado é de consulta. `compras/forms.py` e 16 templates antigos foram removidos; os nomes das rotas antigas foram preservados. Ações legadas de alteração de status/finalização direcionam à revisão React, sem executar mutações. A API substitui o uso da função SQL `menor_valor` antiga, cujo filtro permitia cruzar solicitações; registros históricos não foram reprocessados.

Backup privado antes da migration: `.backups/antes_compras_20261104T165121Z.dump`, verificado com pg_restore. Contagens preservadas: 263 fornecedores, quatro unidades, 20 itens, três solicitações, três orçamentos e três linhas de cada tipo. Auditoria de empresa/unidade/fornecedor/solicitação não encontrou divergências nesses vínculos. Isso não certifica os totais nem as escolhas de orçamento históricas.

Validação: 12 testes da API (inclusive rollback de orçamento, isolamento, menor preço restrito, imutabilidade após autorização e permissões); dois cenários Playwright de fluxo completo e fornecedor. Regressão com 141 testes backend e dois cenários de navegador aprovada. Build TypeScript/Vite aprovado.

## Serviços por cliente — React e DRF

O app `servicos` registra uma descrição de serviço vinculada a cliente; é separado do catálogo `produtos`. Tela `/clientes/app/servicos`; API `/servico/api/servicos/` e opções de clientes em `/servico/api/opcoes/`. CRUD, busca por descrição/cliente, filtro de cliente, paginação, detalhes e permissões de ação no React.

JWT/sessão com CSRF de sessão; empresa e usuário responsável são definidos pelo servidor. Listagem, detalhes, edição e exclusão respeitam empresa e UF do usuário. O cliente informado deve pertencer à mesma empresa e UF autorizada. Operadores de Serviços podem consultar opções mínimas de cliente sem receber acesso ao cadastro completo de Clientes. A descrição mantém o limite de 100 caracteres e a unicidade global preexistente do banco. O admin do modelo é de consulta e respeita os vínculos de empresa/UF.

`servicos/forms.py` e quatro templates antigos removidos. URLs antigas mantêm nomes usados por reverse; lista redireciona ao React, criação exige POST, edição PUT/PATCH e exclusão DELETE. O antigo template incorreto de edição de chaves deixa de ser utilizado. Nenhuma mudança de schema ou migration foi necessária. Auditoria local: um serviço, com empresa e cliente consistentes; nenhum dado real foi modificado.

Testes: sete cenários de API para permissões, empresa, UF, opções mínimas, CRUD, campos protegidos, unicidade, CSRF e métodos legados; regressão junto aos 23 testes de Clientes. Cenário Playwright cria, edita, consulta e exclui um serviço em banco de testes isolado.

## Agenda — contatos, e-mails e telefones

Tela `/clientes/app/agenda`; API `/agenda/api/contatos/` com CRUD, busca por nome/cargo/cliente, filtro de cliente e paginação; opções mínimas em `/agenda/api/opcoes/?tipo=clientes|ufs|municipios`. Autenticação JWT/sessão, CSRF de sessão, permissão de Contato por ação e empresa obrigatória. O escopo é derivado de `contato.cliente.empresa` e da UF do cliente quando o usuário tem restrição. Contatos sem cliente e telefones sem contato são preservados, sem exposição na API comum. O admin de consulta permite ao superusuário inspecionar órfãos para revisão explícita; não atribui empresa automaticamente.

Contato exige cliente autorizado e nome; município deve pertencer à UF. E-mails e telefones são listas `emails: [{id?, email}]` e `telefones: [{id?, fone}]`, no máximo 50 registros cada. Listas omitidas em PATCH permanecem intactas; listas fornecidas substituem o conjunto, atualizando IDs existentes e removendo apenas os omitidos. IDs devem pertencer ao contato. Repetições são rejeitadas; e-mails são comparados sem diferença de caixa e telefones por dígitos. Telefone aceita 8–15 dígitos, formatação e no máximo 16 caracteres, conforme schema legado.

Contato e filhos confirmam ou revertem juntos. Exibir cada lista exige `view_email`/`view_telefone`; inserção, mudança e remoção exigem a permissão correspondente do modelo filho, inclusive na exclusão do contato. Apenas `change_contato` não permite alterar dados de comunicação. A tela oculta listas não autorizadas e mantém o ID de cada linha ao editar. O admin dos três modelos é somente leitura.

`agenda/forms.py` e cinco templates antigos removidos; as listas legadas direcionam ao React e as URLs de criação/edição mantêm nomes usados por reverse, com métodos próprios da API. A exclusão é disponibilizada apenas pela API DELETE com verificações de permissão. O modelo recebeu validação sem alteração de schema: nenhuma migration necessária. Auditoria local: zero contatos, e-mails e telefones; nenhum dado real inserido pela migração. As fixtures de teste usam banco isolado.

Validação: nove testes de Agenda mais regressão de Serviços/Clientes (39 testes backend), um cenário Playwright de criação/edição/consulta/exclusão com e-mail e telefone, e build TypeScript/Vite.

## Chaves de serviços — React e DRF

Tela `/clientes/app/chaves`; CRUD `/chave/api/chaves/`; ação POST `/{id}/atualizar/` para recalcular e opções mínimas em `/chave/api/opcoes/?tipo=clientes|servicos`. A opção de serviço aceita filtro de cliente. Busca por cliente/serviço; API filtra também cliente, serviço, competência e exercício. A tela exibe chaves abreviadas, permite cópia e consulta completa nos detalhes, seleção de mês/ano, edição, recálculo com confirmação e exclusão.

Autenticação JWT/sessão com CSRF de sessão. Permissões padrão reais `chaves.{view,add,change,delete}_chaveservico`; `chaves.view_chaves` continua aceito apenas para leitura, inclusive navegação React e opções. Os nomes antigos inexistentes `add_chaves`/`change_chaves`/`delete_chaves` deixam de ser usados. Recálculo exige change, corrigindo a ação legada que permitia atualização com permissão de leitura. Cliente e serviço devem pertencer à empresa/UF autorizada, e o serviço deve estar vinculado ao cliente. Registros antigos sem serviço ou com vínculo divergente ficam fora da API comum e são inspecionáveis por superusuário no admin de consulta.

Competência é normalizada para 01–12 e exercício aceita 1900–9999. A migration 0005 troca somente o ano padrão fixo de 2018 pelo ano corrente. Chave, data/hora com timezone e usuário são calculados no servidor e não aceitam edição do cliente HTTP. Gravação bloqueia serviço e cliente; o bloqueio do cliente serializa tentativas de duplicar cliente/serviço/competência/exercício. A unicidade global de `chave` continua protegida pelo banco. Recálculo é determinístico e mantém o valor quando os dados de origem não mudaram.

Compatibilidade: preservado o MD5 legado da concatenação exata de descrição do serviço + CNPJ cadastrado + competência com dois dígitos + exercício + segredo de integração, codificada em ASCII. Não normaliza CNPJ nem rotaciona chaves antigas. Cliente sem CNPJ ou descrição fora de ASCII resulta em erro de validação explícito. Este protocolo antigo não é substituto da autenticação JWT da API administrativa; sua modernização exige coordenação com os consumidores externos. O endpoint externo `api/libera_servicos` permanece no app API, e sua compatibilidade foi verificada com dados e segredo sintéticos no teste local (sem chamada externa).

`chaves/forms.py` e quatro templates antigos removidos; URLs antigas conservam nomes de reverse, lista direciona ao React, escrita usa os métodos próprios da API. Admin somente de consulta. Backup privado `.backups/antes_chaves_20261104T173018Z.dump`, verificado com pg_restore antes da migration. Snapshot dos oito registros permaneceu idêntico depois da migration: nenhum sem serviço, vínculo divergente, competência inválida ou grupo duplicado na auditoria local.

Validação: 11 testes de Chaves mais regressão de Serviços e Clientes (41 testes backend), cenário Playwright de geração/edição/recálculo/consulta/exclusão e build TypeScript/Vite aprovados.

## Empresas — cadastro, logo e seleção ativa

Tela `/clientes/app/empresas`; CRUD `/empresa/api/empresas/`, opções `/empresa/api/opcoes/?tipo=ufs|municipios` e POST `/empresa/api/selecionar/`. A API de cadastro lista somente empresas vinculadas ao usuário, independentemente da seleção ativa. Exige as permissões reais `empresa.{view,add,change,delete}_empresa` por ação. Usuários autorizados a criar podem cadastrar sua primeira empresa sem vínculo anterior; a criação adiciona somente o criador à nova empresa, na mesma transação. Não gerencia vínculos de terceiros. Exclusão de empresa com registros protegidos resulta em 409.

CNPJ, razão social e município/UF são validados no servidor. Duplicidade de CNPJ é conferida sem pontuação, com bloqueio transacional PostgreSQL por CNPJ para serializar escritas desta API. Os textos cadastrados são preservados sem normalização automática, inclusive para compatibilidade com integrações existentes. `cnpj_valido` sinaliza cadastros antigos para revisão, sem modificá-los. Um CNPJ inválido precisa ser corrigido explicitamente antes de salvar alterações.

Logo opcional: PNG, JPEG ou WebP validado pelo conteúdo, até 5 MB, com nome UUID e extensão derivada da imagem. O formulário envia multipart quando há arquivo; alterações JSON sem arquivo preservam a logo. `remover_logo` limpa somente a referência. Imagens anteriores não são apagadas automaticamente, pois podem ser referenciadas por documentos antigos. A logo da empresa é exibida no cadastro/detalhes; a marca global Layout Sistemas continua no shell.

A seleção ativa é verificada pelo servidor contra os vínculos do usuário antes de alterar sessão. A rota legada `empresa/select_empresa/` aceita `empresa_select`, mantém `retorno: ok` em sucesso, exige POST e conserva CSRF da autenticação de sessão. O seletor React também usa a validação no servidor e só altera a seleção local após sucesso. Cadastro/edição/exclusão recarregam o perfil para atualizar opções e nomes no seletor; uma empresa recém-criada passa a ser a ativa. Excluir a empresa ativa limpa sua sessão e a interface escolhe uma empresa restante autorizada.

`empresa/forms.py` e cinco templates antigos removidos. O seletor de empresa fica no React e usa a rota segura de seleção; o template compartilhado antigo foi removido na limpeza final. URLs antigas de cadastro mantêm nomes usados por reverse e métodos próprios de API. Admin de empresas somente consulta os vínculos do usuário. Models receberam validação sem alteração de schema: nenhuma migration necessária.

Auditoria local: duas empresas, ambas com logo; um CNPJ antigo inválido, nenhum grupo de CNPJ duplicado e nenhuma divergência município/UF. Dados e imagens reais foram preservados. A tela sinaliza o CNPJ que precisa de revisão. Os uploads e cadastros de teste usam banco separado e armazenamento temporário.

Validação: regressão com 179 testes backend e 11 cenários Playwright (Empresas, Contas, Contratos, Notas, Clientes), mais teste específico da sinalização do CNPJ legado (total de 12 testes de Empresas); quatro testes frontend de autenticação e build TypeScript/Vite aprovados. O cenário Empresas cobre upload, nomes no seletor, edição, exclusão, leitura e primeiro cadastro. Emissão/e-mails nos testes fiscais usam integrações simuladas/local, sem operações externas.

## Configuração de ambiente fiscal — React e DRF

Tela `/clientes/app/ambiente-fiscal`; API `/configambiente/api/ambientes/`. Um ambiente por empresa selecionada, JWT/sessão, CSRF de sessão e permissões de visualizar/adicionar/alterar Ambiente. Edição legada mantém o nome de reverse e métodos JSON/multipart próprios da API; lista antiga direciona ao React. `configambiente/forms.py` e o único template deste app foram removidos; o template global edit.html foi removido na limpeza final, após concluir a migração dos demais módulos. O admin do ambiente é de consulta e exclui senha/certificado.

Certificado e senha são exclusivamente de escrita na API. Consulta retorna indicadores de cadastro/disponibilidade, sem senha, caminho, arquivo ou URL de download. Novos arquivos PKCS#12 de até 5 MB precisam conter chave privada RSA e certificado dentro da validade, abrir com a senha informada e possuir chave pública correspondente. Esta é uma verificação local de integridade/formato/validade; não verifica titular, cadeia de confiança, revogação ou habilitação junto ao provedor. O responsável fiscal deve conferir esses requisitos antes de operar. Sem arquivo válido, a emissão continua bloqueada pelos pré-requisitos de Notas.

`PrivateCertificateStorage` armazena os novos arquivos com nomes UUID em `.private/certificados/` (ou `PRIVATE_CERTIFICATE_ROOT` definido nas configurações Django), com arquivos 0600 e diretórios 0700, fora de MEDIA_ROOT e sem URL pública. O integrador fiscal passou a localizar o armazenamento privado, mantendo leitura de referências legadas para compatibilidade. Nenhum arquivo real foi enviado/movido nesta migração: o certificado configurado no banco local já estava ausente. Arquivos anteriores não são apagados em substituições; falha posterior à gravação remove somente o novo arquivo. Inclua o diretório privado no backup e dê acesso somente ao usuário do processo Django.

A senha agora é persistida com Fernet em `CertificatePasswordField`, com chave derivada da SECRET_KEY e separação de contexto. A migration 0014 amplia o campo e criptografa as credenciais preexistentes. A aplicação continua recebendo texto puro do campo ORM para o integrador, e a API nunca o serializa. Campo de senha omitido ou vazio sem novo certificado preserva a senha atual. Para certificado sem senha, reenvie o arquivo com senha vazia para validação explícita. A substituição da senha exige validar o certificado existente ou reenviar o arquivo.

**Recuperação:** preserve a SECRET_KEY, o banco e os arquivos privados juntos. Antes de rotacionar a chave principal, configure as anteriores em SECRET_KEY_FALLBACKS (lista em variável de ambiente suportada nas settings) para permitir leitura das credenciais antigas; novas gravações usam a chave atual. Sem as chaves corretas, a credencial criptografada não pode ser lida. A migração de dados não tem reversão automática para texto puro: rollback exige planejamento e backups compatíveis. Backup do banco anterior à migração em `.backups/antes_ambiente_fiscal_20261104T185216Z.dump`; cópia privada das chaves de recuperação em `.backups/ambiente_fiscal_20261104T185216Z.keys.json`, 0600, sem conteúdo exibido nas ferramentas. Ambos ficam fora do Git. Trate o backup anterior como sensível, pois corresponde ao esquema legado.

Transição para produção exige `confirmar_producao: true`. Gravações bloqueiam quando existem operações fiscais executando/incertas. Reserva de operações de Notas usa o mesmo bloqueio de Ambiente, com nova conferência local dos pré-requisitos dentro da transação; assim, configuração e reserva não passam uma pela outra usando credenciais antigas. A transmissão permanece fora da transação, e a operação reservada impede alteração de configuração enquanto estiver em execução/incerta. Esta migração não transmite notas nem altera o ambiente real de produção/homologação.

Contadores são de consulta no CRUD. POST `/{id}/ajustar_sequencias/` exige `change_ambiente` mais a nova permissão `configambiente.ajustar_sequencias_ambiente`, confirmação explícita e ambos os valores. Não permite redução ou valor inferior ao maior número reservado no histórico de notas; limite 2.147.483.646 para ajuste. Criação de novo ambiente parte dos maiores números do histórico. `prontidao` retorna diagnóstico local, sem transmissão. Auditoria registra usuário e mudanças de metadados/contadores; alterações de credenciais aparecem somente como indicadores, sem valor anterior/novo e sem serializar o objeto completo.

Auditoria local: uma configuração em produção, zero certificados disponíveis; configuração e 30.281 notas preservadas. Snapshot do conteúdo lógico permaneceu idêntico após criptografia, e o banco passou a armazenar somente senha vazia ou ciphertext. A consulta com o usuário normal da aplicação foi verificada sem exposição de credenciais; nenhuma migration pendente.

Validação: 13 testes de Ambiente (criptografia/rotação, arquivo privado/PKCS#12, sigilo, permissões, produção, bloqueios, histórico de sequência e rollback); regressão com 193 testes backend; dois cenários Playwright de Ambiente e dois de Notas aprovados. Certificados e operações fiscais nos testes são sintéticos/simulados. Build TypeScript/Vite aprovado.

## Usuários — perfil e segurança da conta

Tela `/clientes/app/perfil`, disponível a qualquer usuário autenticado, inclusive sem empresa ou permissão de cadastro. API `/usuario/api/perfil/` permite consultar/atualizar exclusivamente o próprio perfil com `UsuarioSerializer(ModelSerializer)`. CPF, telefone, e-mail e paginação são validados no servidor. Alterar o e-mail exige confirmação da senha atual. Senha, grupos, permissões, empresas, UF e privilégios administrativos não são expostos nem editáveis nesta API. Avatar PNG/JPEG/WebP até 5 MB recebe nome UUID; omissão preserva o arquivo e remoção é lógica. Falhas descartam somente o novo arquivo; imagens anteriores permanecem preservadas.

POST `/usuario/api/perfil/senha/` exige senha atual, nova senha e confirmação, com validadores Django e mínimo de 12 caracteres. A alteração invalida access e refresh tokens anteriores, sessões Django e links de recuperação. Access continua com TTL de cinco minutos; refresh, um dia com rotação e blacklist. `CHECK_REVOKE_TOKEN` e o serializer específico de refresh verificam o marcador do hash da senha. Tokens emitidos antes desta mudança, sem marcador, exigem novo login. Senhas atuais não foram alteradas e continuam aceitas; a exigência de tamanho se aplica às novas senhas.

Login/refresh React também estabelecem a sessão Django para compatibilidade com os módulos legados, mantendo a empresa selecionada autorizada. Login retorna o CSRF atualizado após a rotação. Logout POST encerra ambas as sessões; GET legado apenas abre a confirmação React em `/clientes/app/sair`. O estado React descarta respostas atrasadas de sessão depois da saída ou troca de senha. DRF agora usa `IsAuthenticated` como permissão global; login, CSRF e recuperação declaram acesso público explicitamente.

Recuperação em `/clientes/app/recuperar-senha`, com POSTs `/usuario/api/recuperacao/solicitar/` e `/confirmar/`. Solicitação exige usuário e e-mail; contas inexistentes, inativas ou sem senha local recebem a mesma resposta pública. Links aleatórios expiram em 30 minutos, são de uso único e ficam no fragmento da URL, removido pela interface, para não enviar o token no GET inicial. O banco armazena somente um digest vinculado ao hash atual da senha. Troca de senha por admin/CLI também invalida links anteriores. A validade é conferida no POST de confirmação, dentro de transação com bloqueio do usuário. Há CSRF e limites por IP/identidade; configure cache compartilhado entre processos na produção para que os limites sejam compartilhados. Respostas têm conteúdo uniforme; o envio SMTP é síncrono e não garante uniformidade de tempo. Falha de entrega reverte a solicitação e mantém a resposta genérica, sem registrar tokens ou credenciais.

Para habilitar envio real, configure `PUBLIC_APP_URL` com a origem pública (HTTPS em produção, sem caminho) e as variáveis `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`/`EMAIL_USE_SSL` e `DEFAULT_FROM_EMAIL` conforme o provedor. A origem não vem do Host da requisição. Sem configuração válida, a recuperação responde 503 para todas as contas. **O ambiente local ainda não possui recuperação por e-mail configurada.** Nenhum e-mail real foi enviado na migração; os testes usam caixa local em memória. O helper SMTP legado com credencial embutida foi removido; a credencial antiga precisa ser rotacionada no provedor, pois excluir o arquivo não revoga seu valor nem apaga o histórico Git.

`usuario/forms.py`, quatro templates próprios e `usuario/envia_email.py` foram removidos. Administração de privilégios permanece no Django Admin, restrita a superusuário. O cadastro operacional de contas comuns está disponível também na tela descrita na seção “Cadastro de usuários e perfil no cabeçalho”. Auditoria do perfil registra apenas nomes de campos alterados, sem senha, hash ou token. A migration 0013 adiciona índices de recuperação, torna nome/sobrenome opcionais e desativa links legados; a reversão não reativa esses links. Backup privado verificado: `.backups/antes_usuarios_20261104T195845Z.dump`. Snapshot confirmou preservação de todos os usuários, hashes, permissões, grupos, empresas e registros históricos de recuperação; havia zero links antigos ativos. Nenhuma migration pendente após aplicação, e o login restrito do PostgreSQL foi mantido.

Validação específica: 20 testes backend de Usuários e 23 de Clientes; quatro cenários Playwright de perfil, senha, recuperação e logout legado; seis testes frontend de autenticação e build TypeScript/Vite aprovados. Todas as contas, imagens e mensagens destes testes usam fixtures e armazenamento isolados.

Regressão desta etapa: 207 testes backend dos apps migrados e 27 cenários Playwright aprovados. O cenário de Notas inicialmente interagia com o formulário anterior durante a transição de criação para edição; passou após aguardar o formulário correto e seus dados. Reexecução isolada também confirmou os 20 testes de Usuários após a correção que preserva o avatar anterior em requisição conflitante de envio/remoção. Verificação com runtime restrito: SPA 200, perfil anônimo 401, nenhuma migration pendente.

## Dashboard — visão geral com dados reais

Tela `/clientes/app/dashboard`, item **Visão geral**; API GET `/dashboard/api/resumo/`. As URLs `/dashboard/` e `/dashboard/dashboard/` (inclusive o nome de reverse `dashboard`) direcionam para o React. Para contas com indicadores autorizados, o painel passa a ser o destino padrão da SPA. A paleta vermelho/branco/preto e a logo Layout Sistemas foram preservadas. `dashboard/forms.py` e os três templates do app foram removidos. Alertas e competência ficam no painel React. O template compartilhado antigo home.html foi removido na limpeza final, com páginas de erro independentes do layout legado.

JWT/sessão com `IsAuthenticated`, CSRF nas escritas autenticadas por sessão e respostas `no-store`. A empresa é validada por vínculo em `empresa_da_requisicao`; dados são filtrados também pela UF do usuário. Clientes, notas, receitas e alertas exigem, respectivamente, `clientes.view_cliente`, `notas.view_nota`, `financeiro.view_docreceita` e `contratos.view_contrato`. Distribuição por parceiro exige visualizar clientes e parceiros. Seção não autorizada retorna `null`, sem contagens ou valores. Sem nenhuma dessas permissões, o resumo responde 403 e o menu não oferece o painel; o perfil continua acessível. Contratos com cliente de outra empresa e notas com vínculos divergentes são excluídos dos indicadores, sem reatribuir registros legados.

Não existe tabela/modelo próprio do Dashboard: os ModelSerializers de contratos e parceiros expõem somente os campos necessários aos alertas/distribuição, e o ModelSerializer de Usuario aceita somente mês/ano da preferência pessoal. O serializer do resumo reúne os agregados. Nenhum modelo/schema foi artificialmente criado para armazenar indicadores calculados; nenhuma migration necessária.

Competência pessoal em GET/PATCH (ou POST) `/dashboard/api/competencia/`, campos `mes` (1–12) e `ano` (1900–9999). A atualização bloqueia somente o próprio usuário, grava apenas `ultimo_mes`/`ultimo_ano` e audita os nomes dos campos. Não exige permissão administrativa nem empresa. GET preserva preferências existentes; valor legado inválido usa mês/ano atuais na resposta, sem gravar. A interface só aplica a nova preferência após confirmação do servidor. A antiga `/dashboard/competencia/` aceita GET para redirecionar; POST antigo responde 405, evitando alteração por formulário descontinuado.

Indicadores:

- Clientes cadastrados/ativos: posição atual da empresa/UF, independente da competência. O número fixo de exemplo de “novos clientes” foi descartado: o cadastro não possui data de criação que permita calcular esse indicador com precisão.
- Notas: contagens do mês/ano de competência fiscal e série anual de 12 meses, incluindo meses vazios. “Cadastradas” inclui rascunhos e canceladas; não implica emissão/autorização fiscal. “Com pagamento registrado” é o marcador `dt_data_pagamento` da nota, sem confundir com valor recebido. Não utiliza o mês da data de emissão como competência.
- Receitas: documentos com vencimento no mês selecionado, valor total, recebimentos registrados até o momento, saldo, saldo vencido hoje e saldo que vence de hoje até dez dias. Valores são calculados em Decimal a partir de `RecReceita`, com subconsulta por documento para não multiplicar valores em baixas parciais. Não usa o cache legado `valor_recebido` nem o marcador da nota como fonte de saldo. Saldo pendente é limitado a zero por documento. O quadro não representa fluxo de caixa de recebimentos ocorridos no mês, e a interface explica o recorte.
- Parceiros: dez maiores por quantidade de clientes visíveis, percentual sobre todos os clientes visíveis e quantidade sem parceiro autorizado. Parceiros de outra empresa/UF não têm identidade exposta; empresa vazia não provoca divisão por zero.
- Alertas: contratos ativos do exercício selecionado que vencem de 30 dias antes a 30 dias depois de hoje; o intervalo aparece na tela. Dez itens por página, ordenados por vencimento/ID. O mês de competência não altera esta janela baseada em hoje.

Verificação no banco existente em transação somente de leitura, com o runtime restrito: API 200, acesso anônimo 401, série anual completa, nove consultas no resumo da conta conferida e aproximadamente 168 ms nesta execução local (não é garantia de desempenho). Nenhum usuário, preferência, registro financeiro ou fiscal real foi modificado; zero migrations pendentes. Não houve operação fiscal, bancária ou envio de e-mail real.

Validação: 13 testes backend específicos do Dashboard (permissões por seção, empresa/UF e vínculos inconsistentes, competência/CSRF, limites/paginação, meses vazios, saldo parcial e estorno); regressão com Clientes, Usuários, Financeiro, Contratos e Notas, totalizando 116 testes backend aprovados entre as execuções. Três cenários Playwright de Dashboard mais oito de Clientes/Usuários/Empresas aprovados; seis testes frontend de autenticação e build TypeScript/Vite aprovados. Os testes usam contas e valores sintéticos em PostgreSQL isolado. Capturas desktop/mobile em `/tmp/gestao-dashboard-e2e/`; o Chromium de testes pode ser reinstalado com `PLAYWRIGHT_BROWSERS_PATH=/tmp/gestao-playwright node_modules/.bin/playwright install chromium --only-shell` se o diretório temporário for limpo.

## Recadclientes — entidades e responsáveis

Tela `/clientes/app/recadastramento`, item **Recadastramento**, com abas de Entidades, Usuários da entidade, Contadores, Controladores, Prefeitos e Vice-prefeitos. Este app era um esboço desabilitado, com forms/views/URLs vazios e seis modelos sem tabelas no banco; agora possui cadastro administrativo autenticado em React/DRF. Não havia templates próprios para remover. `recadclientes/forms.py` foi excluído, e o app foi incluído nas settings e nas URLs. A rota `/recadclientes/` direciona ao React. A Visão geral permanece antes do novo módulo no menu e como destino padrão das contas que possuem acesso ao Dashboard.

CRUDs em `/recadclientes/api/entidades/`, `/usuarios/`, `/contadores/`, `/controladores/`, `/prefeitos/` e `/vice-prefeitos/`. JWT/sessão, CSRF para escrita por sessão, paginação, busca e filtro por cliente (entidades) ou entidade (responsáveis). Cada ação exige `recadclientes.{view,add,change,delete}_{entidaderecad,usuariorecad,contadorrecad,controladorrecad,prefeitorecad,viceprefeitorecad}` conforme o modelo. As abas e os botões seguem essas permissões. O acesso é derivado de `entidade.cliente.empresa` e da UF do cliente; consultar/alterar/excluir ID fora do escopo resulta em 404, referência estrangeira no corpo resulta em validação, e seleção de empresa não vinculada resulta em 403.

O serializer de entidade projeta seus próprios campos e nomes de cliente/UF/município. Pessoas não são serializadas dentro da entidade, preservando a separação das permissões de cada tipo. Um usuário autorizado somente a contadores pode usar essa aba sem consultar o cadastro completo da entidade. Opções mínimas e paginadas em `/recadclientes/api/opcoes/?tipo=clientes|entidades|ufs|municipios`, com filtro `id`, busca e UF de município. A permissão do formulário correspondente é exigida para essas opções; nomes de entidade necessários ao vínculo não incluem telefone/e-mail dos responsáveis.

`serializers.py` usa ModelSerializer por meio de CleanSerializer e validação de modelo. Cliente e nome da entidade são obrigatórios; nome completo e entidade são obrigatórios para cada responsável. Município deve pertencer à UF; telefone aceita 8–15 dígitos e até 15 caracteres conforme o campo; e-mail e site HTTP/HTTPS são validados no servidor. Código e tipo continuam campos livres de até quatro caracteres: nenhum domínio de códigos foi presumido. Cargo pertence somente a Usuários da entidade, que representam contatos, sem credenciais de login. Os modelos permitem múltiplos registros por tipo de responsável.

O cliente da entidade é definido na criação e fica imutável na API, mantendo o escopo dos responsáveis. Operações de escrita são transacionais. Exclusão de entidade com responsáveis vinculados retorna 409 e preserva os filhos; exclusão individual exige a permissão do respectivo modelo. Respostas dos cadastros têm `Cache-Control: no-store`. Auditoria registra alterações pelos modelos; o Django Admin deste app é somente de consulta e segue empresa/UF do usuário. A interface prepara o formulário antes da abertura para preservar seleção de entidade ao alternar entre abas.

A migration inicial cria seis tabelas (`entidade_recad`, `usuario_recad`, `contador_recad`, `controlador_recad`, `prefeito_recad`, `viceprefeito_recad`) com FKs protegidas. Corrigidos os nomes reversos repetidos do esboço para coleções distintas. Não houve importação de dados de exemplo. O cadastro usa as APIs DRF deste app; a rota `api/recad_delphi` pertence ao módulo de integrações e possui contrato próprio.

Backup privado `.backups/antes_recadastramento_20261105T175915Z.dump`, catálogo verificado com pg_restore antes da migration. Migração aplicada e zero migrations pendentes. Snapshot confirmou hashes/senhas, usuários, vínculos de empresas/grupos/permissões e contagens dos módulos preexistentes preservados. As seis tabelas novas permanecem vazias no banco atual. Foram criadas 24 permissões de modelo; usuários comuns precisam recebê-las pelo administrador conforme suas funções, sem concessão automática de privilégios. Superusuários seguem as regras padrão de permissões do Django e o escopo empresarial das APIs.

Validação: 13 testes backend de Recadclientes e regressão de todos os apps migrados, total de 233 testes backend aprovados; três cenários Playwright deste app e seis de Dashboard/Empresas aprovados, além de seis testes frontend de autenticação e build TypeScript/Vite. O cenário completo cobre entidade, cinco tipos de responsável, edição, proteção de exclusão, remoção individual, detalhes, troca de empresa e layout mobile; os demais cobrem consulta de entidade e acesso somente a contadores. Todos os cadastros e contatos de teste são sintéticos em banco separado; capturas em `/tmp/gestao-recad-e2e/`.

## API de integrações — contratos legados em DRF

O módulo `api` já era acessado por sistemas externos em `/api/`. Suas views passaram para APIView do DRF, com serializers de entrada e ModelSerializers de projeção de Cliente, Nota, Liberacao e ChaveServico. As regras de negócio estão em `api/services.py`. O módulo não possui tabela, formulário ou tela próprios; não foi criado outro cadastro React. URLs e nomes de reverse permanecem os mesmos.

Os consumidores Delphi/serviços continuam autenticando cada POST pela assinatura própria do protocolo, sem usar cookies ou JWT. As views declaram esse acesso explicitamente e conferem a assinatura antes de consultar dados ou gravar. Credenciais de sessão/JWT e cabeçalhos de empresa não substituem a assinatura nem mudam a identidade assinada. O cadastro administrativo React continua sob as permissões/autenticação de seus respectivos apps. O endpoint público de consulta por município mantém somente CNPJ, instituição e código de entidade, sem dados pessoais ou financeiros.

Contratos preservados para POSTs válidos:

| Rota | Entrada e assinatura |
| --- | --- |
| `/api/libera_delphi/` | `codigo`, `codigo_layout`, `competencia=MMYYYY`, `key=MD5(codigo_layout + codigo + competencia + API_SECRET_KEY)` |
| `/api/bloqueia/` | Mesma assinatura; aceita também competência `YYYY`, convertida em dezembro somente depois da autenticação |
| `/api/libera_transparencia/` | `codigo`, `codigo_layout`, `tipo` 1 (transparência, padrão) ou 2 (contracheque), `key=MD5(codigo_layout + codigo + tipo + API_SECRET_KEY)`; competência corrente do servidor |
| `/api/libera_servicos/` | `servico`, `cnpj`, `competencia=MMYYYY`, `key=MD5(servico + cnpj + competencia + API_SECRET_KEY)` |
| `/api/libera/` | `codigo`, `codigo_layout`, `competencia=MMYYYY`, `key=SHA256(codigo_layout + codigo + competencia + API_SECRET_KEY + DDMMAAAA)` |
| `/api/cod_entidade/` | `municipio` com sete dígitos IBGE; resposta pública em lista com três campos |
| `/api/recad_delphi/` | Assinatura de competência Delphi e `dados` opcional até 64 KiB; preserva reconhecimento `{}` sem persistência de recadastramento |

As concatenações usam ASCII, sem normalizar CNPJ, descrição, espaços ou códigos. MD5 aceita hexadecimal em maiúsculas/minúsculas; SHA256 mantém comparação em minúsculas. Mês deve estar entre 01 e 12 e o ano deve ser válido. Parâmetros ausentes não recebem mais valores fictícios de 2017/2018. Entradas inválidas e assinaturas incorretas preservam o envelope legado `error` com HTTP 200; município inválido retorna lista vazia. Métodos diferentes de POST retornam 405, e falhas de configuração/banco retornam 503 sem conceder acesso. JSON, formulário e multipart são aceitos. Respostas usam `no-store` e `nosniff`; há limite de IP (`REMOTE_ADDR`) configurável por `API_LEGACY_RATE`, padrão 600/min, com 429 ao exceder. Na produção, configure cache compartilhado ou limite no gateway para unificar a contagem entre processos; atrás de proxy, confira qual endereço chega como REMOTE_ADDR.

O endpoint SHA256 mantinha a consulta histórica com `codigo`/`codigo_layout` invertidos em relação ao Delphi; essa diferença foi preservada e testada, e o erro de `datetime.today()` foi corrigido. Respostas de liberação mantêm os campos `liberado`, `usuario`, `data_liberacao`, `key` e, quando necessário, `notas`. As variantes de chave de resposta com/sem data foram preservadas conforme o ramo do protocolo. A chave persistida da liberação segue layout + código + competência + ano + “sucesso” + segredo. Datas históricas usam a representação JSON anterior; nova liberação responde com a data corrente e armazena horário com timezone. Valores de nota continuam strings decimais. Links de nota usam PUBLIC_APP_URL quando configurada e o domínio legado como fallback; a abertura segue a proteção administrativa de Notas.

A criação automática de liberação ocorre em transação com bloqueio do cliente. Solicitações concorrentes reutilizam a mesma liberação; falha posterior à inserção reverte a operação. `API_INTEGRATION_USER_ID` configura o usuário de registro (padrão 11 preservado do legado), que deve existir e estar ativo; sua ausência impede somente novas liberações automáticas. O usuário de registro não substitui a autenticação assinada do consumidor. A configuração financeira continua em `Configuracao(pk=1)`. Foram mantidas a regra do limite de notas abertas, a situação financeira `R`, a liberação manual existente e a exceção de parceiro válido da mesma empresa. A liberação de competência respeita `gerar_notas=False` antes dessa exceção. Falhas de banco/configuração não são ignoradas nem transformadas em autorização.

Consultas agora vinculam a liberação ao cliente resolvido, e notas/serviços precisam ter os vínculos empresariais corretos. Cliente inexistente, inativo, desativado, sem empresa ou com identidade de integração ambígua não recebe liberação. Chaves de serviço duplicadas para a mesma identidade/período também são negadas. Bloqueios de competência usam filtros ORM parametrizados; em períodos sobrepostos, prevalece a restrição de cada flag, sem escolher uma linha arbitrária. O endpoint de recadastramento deixou de imprimir `dados` no console; a assinatura e o conteúdo recebido são marcados como sensíveis nos relatórios de erro. O cadastro administrativo Recadclientes continua usando suas próprias APIs autenticadas.

API_SECRET_KEY foi externalizada para variável de ambiente, preservando o valor local anterior: nenhuma chave existente foi rotacionada. Clientes e Financeiro passaram a consultar `django.conf.settings`, como as integrações e os geradores de Chaves, garantindo configuração consistente e isolamento dos testes. Em outro ambiente, forneça o mesmo segredo atualmente contratado com os consumidores antes de iniciar a aplicação. A SECRET_KEY do Django e as chaves de criptografia fiscal não foram alteradas. A credencial antiga ainda existe no histórico Git: planeje rotação coordenada com os consumidores e evolução do protocolo MD5; esta etapa preserva compatibilidade, sem apresentar MD5 como autenticação moderna.

Backups privados de configuração, fora do Git e com modo 0600: `.backups/antes_integracoes_20261105T184506Z.env` (ambiente antes da externalização) e `.backups/integracoes_configuradas_20261105T185524Z.env` (ambiente atual, incluindo a chave externalizada). Para recuperar a versão atual, preserve a configuração atual com a chave; restaurar somente o arquivo de ambiente anterior junto às settings novas pode deixar a variável ausente. Nenhum conteúdo de credencial foi incluído nesta documentação.

Auditoria do banco atual, somente em leitura: configuração financeira e usuário legado existem; foram encontrados dez grupos de pares de códigos de cliente duplicados, 41 grupos com mais de uma liberação por cliente/competência/ano e 491 liberações com códigos divergentes do cadastro atual do cliente. Os dois últimos indicadores não comprovam duplicidade da tupla completa usada pelo protocolo: exigem revisão do histórico. Nenhum cadastro, liberação, código ou vínculo real foi alterado; identidades ambíguas são negadas em vez de escolher outro cliente. A revisão dos dados legados permanece uma ação administrativa explícita.

Validação: 24 testes específicos das integrações, incluindo vetores das assinaturas antigas, envelopes/tipos, entradas inválidas sem consulta ao banco, duplicidades, bloqueios, escopo, falhas com rollback, ausência de dados pessoais no console e duas requisições simultâneas criando uma única liberação. Regressão completa com 257 testes backend aprovados e dois cenários Playwright de Clientes/Chaves aprovados. Assinaturas, usuários e liberações destes testes são sintéticos em banco isolado. No banco atual, a chave foi comparada à configuração anterior sem exibir seu valor, e os sete endpoints foram conferidos apenas com entradas incompletas em transação somente de leitura. Nenhuma liberação real criada; zero migrations pendentes.

## Conclusão da sequência de apps e limpeza compartilhada

Os módulos funcionais previstos já possuem suas telas React/APIs DRF ou, no caso das integrações externas, os contratos de máquina migrados para DRF. A etapa seguinte concluiu o legado compartilhado de apresentação, sem criar outro app de negócio. `core/api.py` continua sendo a fronteira compartilhada de seleção/autorização de empresa. As bibliotecas fiscais mantêm sua finalidade de integração.

Removidos dez templates globais sem chamadas de execução: base, home, menu, empresas_select, edit, list, partial_form, rel, rel2 e relatorio. Também foram removidos `core/views/basic_views.py`, `core/utils/utils.py` e `layCliente/context_processors.py`, após conferir a ausência de imports dos helpers antigos. A aplicação utiliza os validadores dos models/serializers dos apps e a consulta de CEP já migrada. O registro de widget_tweaks e as configurações/contexto de reCAPTCHA usados apenas nos templates antigos saíram das settings; os controles ativos de autenticação, CSRF e limitação de tentativas continuam nas APIs.

As páginas genéricas de erro Django usam `templates/error_base.html` e templates 400/403/404/500 próprios, com português, vermelho/branco/preto e a logo Layout Sistemas. A página 403 agora apresenta o código e a mensagem corretos. O corpo não mostra exceção, caminho privado, usuário ou sessão. A página 500 renderiza sem acesso ao banco, à sessão, ao usuário ou ao manifesto Vite; as páginas não precisam executar JavaScript. O link de retorno leva à SPA. Os handlers padrão do Django e os erros JSON do DRF continuam responsáveis pelos respectivos tipos de resposta.

Templates necessários à aplicação permanecem: o shell `clientes/templates/clientes_app.html`, a nota pública, a lista pública de notas e o e-mail fiscal. Os arquivos modelo_contrato.html/odt foram preservados como referência documental. O Django Admin usa seus próprios templates. O shell e o HTML de desenvolvimento passaram a ter o título geral “Gestão Financeira · Layout Sistemas”. A montagem das URLs estáticas foi simplificada, removendo a entrada duplicada de mídia em DEBUG.

Validação desta etapa: nove testes de páginas compartilhadas, sem acesso ao banco, mais regressão dos apps — total de 266 testes backend aprovados. Três cenários Playwright de Clientes/Notas aprovados; seis testes frontend de autenticação e build TypeScript/Vite aprovados. O teste de Notas passou a aguardar o fechamento completo do formulário e conferir o texto efetivamente persistido no PATCH; o botão ganhou nome acessível estável durante o carregamento. Não houve mudança de models/schema nem operação no banco atual. Emissão e e-mail dos testes fiscais são simulados/local, em banco isolado.

Esta conclusão se refere à migração e à limpeza de código. Continuam registradas nas seções anteriores as pendências operacionais: configuração do e-mail de recuperação, rotação coordenada das credenciais antigas, revisão dos códigos de integração ambíguos e disponibilidade/validação do certificado fiscal antes de emissão real.

## Navegação organizada conforme o menu legado

A hierarquia foi recuperada de `templates/menu.html` no histórico Git (versão anterior à exclusão em ec084222, comparada também com dc7f1644). A lista plana do menu React foi substituída por grupos expansíveis do Ant Design, mantendo os destinos das páginas atuais. Estrutura centralizada em `frontend/src/navigation.ts`, com renderização e controle de abertura em `components/SidebarNavigation.tsx`.

| Grupo | Páginas, na ordem do menu |
| --- | --- |
| Cadastro | Parceiros, Clientes, Bloqueio de clientes, Produtos, Contatos |
| Movimento | Contratos, Notas fiscais |
| Compras | Unidades de medida, Itens de compra, Fornecedores, Solicitações de compra, Orçamentos de compra |
| Contas Bancos | Bancos, Contas bancárias, Transferências, Movimentações |
| Financeiro | Serviços por cliente, Contas a receber, Contas a pagar, Conciliação bancária, Fechamentos de caixa, Liberações, Chaves de serviços |
| Contábil | Centros de custo, Tipos de despesa, Planos de contas, Lançamentos contábeis |
| Relatórios | Cadastrais, Financeiros, Bancários, Contratos / Notas; acesso geral aos relatórios cadastrais e fiscais |
| Configurações | Empresas, Ambiente fiscal |

Visão geral permanece no início, e Recadastramento e Cadastro de usuário são itens próprios. Meu perfil fica no menu do usuário no canto superior direito. Contatos abre `/agenda`; o destino incorreto do antigo menu para Contratos não foi reproduzido. As operações de emissão/consulta/cancelamento/e-mail continuam nas ações da tela de Notas. Recursos acrescentados durante a migração, como orçamentos e lançamentos contábeis, ficam no grupo correspondente.

Cada grupo mostra apenas páginas já autorizadas pelas permissões atuais, e grupos vazios são omitidos. Usuários com acesso somente à Agenda conseguem abrir Cadastro/Contatos sem precisar de permissões de Clientes. A análise consolidada exige as permissões de receitas, despesas e fechamento e ausência de restrição por UF; conciliação exige visualizar receitas e adicionar recebimentos. As verificações de API continuam no backend.

A página ativa recebe destaque e `aria-current`, e seus grupos ancestrais abrem automaticamente ao acessar a URL, recarregar ou navegar por um atalho. Abertura dos grupos é independente da navegação: no celular, expandir uma pasta mantém o painel aberto; escolher uma página fecha o painel. O menu permite rolagem e quebra dos rótulos longos, com a paleta vermelho/branco/preto e a marca Layout Sistemas.

Relatórios cadastrais e fiscais usam o parâmetro `tipo` já suportado. A troca entre atalhos reinicia o formulário para aplicar o tipo escolhido. Atalhos financeiros usam as telas atuais de receitas/despesas e seus filtros, conciliação, análise e relatórios bancários; trocar de relatório bancário sincroniza o tipo do formulário. Os nomes acessíveis distinguem links de cadastro e de relatório, mesmo quando o rótulo visual é igual.

Validação: 12 testes frontend aprovados (seis de autenticação e seis de hierarquia/permissões/seleção), build TypeScript/Vite e nove cenários Playwright aprovados entre navegação, Clientes, Produtos e Contas. Os testes cobrem a ordem exata de Cadastro, o destino de Contatos, acesso direto, celular, relatórios, conciliação em revisão, troca de tipo bancário e conta com acesso somente a contatos. Capturas em `/tmp/gestao-navigation-e2e/`. Somente fixtures no PostgreSQL isolado; nenhum schema ou registro do banco atual foi alterado.


## Folhas de impressão com identidade Layout Sistemas

Contratos, relatórios cadastrais/fiscais, documentos e análise financeira, registros/extratos bancários e documentos/comparativos de compras compartilham o cabeçalho `components/PrintLayout.tsx` e a folha `static/css/layout-print.css`. Logo, vermelho/branco/preto, empresa selecionada, CNPJ e data de geração identificam o documento. A marca do software é separada do emitente. Notas públicas e sua listagem usam `notas/templates/print_base.html` com o mesmo estilo, preservando a indicação de consulta e o estado de cancelamento. Números/anos fiscais não recebem separador de milhar.

Documentos usam A4 retrato; relatórios e comparativos usam A4 paisagem, cabeçalhos de tabela repetidos e contagem de páginas nos navegadores compatíveis com margens CSS. A análise anual é dividida em quatro trimestres na impressão, mantendo os doze meses, totais e exportação CSV. O botão de impressão seleciona somente a folha desejada; atributos de seleção sobrevivem às atualizações dos painéis React e são removidos ao terminar. Menus, filtros e ações não entram no papel.

A apresentação mantém os dados e as precisões existentes. Não houve mudança de models, schema, regras de autorização ou registros reais. PDFs de conferência em `/tmp/gestao-print-e2e/` usam dados sintéticos em banco de testes isolado. Para conferir a impressão, execute `core.printing_browser_tests` e os testes de navegador de Contratos, Notas, Contas e Compras com `financeiro.pg_test_settings`; emissão/e-mail fiscais são simulados pelos testes. Os testes frontend também verificam seleção, restauração e impressão pelo navegador.

Validação desta etapa: 16 testes frontend, build TypeScript/Vite, 34 testes backend (Core/Notas) e 12 cenários Playwright aprovados. PDFs conferidos em A4 retrato/paisagem, com relatório de 90 linhas em seis páginas e análise anual em quatro páginas. `manage.py check` e `git diff --check` sem problemas.


## Ações em cada tabela

Todas as tabelas das páginas React e dos detalhes usam `components/DataTable.tsx`, com botões **Imprimir tabela** e **Exportar planilha (CSV)**. As ações respeitam as colunas e linhas já apresentadas: página atual nas listagens paginadas e todos os registros exibidos nas tabelas sem paginação. O escopo aparece junto dos botões e na folha impressa. As exportações completas preexistentes dos relatórios continuam disponíveis.

O CSV usa UTF-8 com BOM, separador ponto e vírgula e proteção contra interpretação de fórmulas. Cabeçalhos agrupados recebem nomes compostos. Colunas de ações e controles são omitidas; chaves mascaradas continuam mascaradas e campos internos da API não são serializados. O Excel/LibreOffice pode inferir tipos automaticamente ao abrir um CSV; para manter zeros iniciais, importe essas colunas como texto. Não se trata de arquivo XLSX.

A impressão cria uma folha isolada com o cabeçalho Layout Sistemas, dados da empresa, indicação de página e valores apresentados. Ao encerrar, a folha temporária é removida. Os botões ficam indisponíveis durante o carregamento e em tabelas vazias. As quatro tabelas trimestrais exclusivas do papel não recebem controles duplicados. A lista pública de notas também ganhou CSV, usando somente o conteúdo da consulta assinada.

Validação: 20 testes frontend, build TypeScript/Vite, 34 testes backend Core/Notas e 11 cenários de navegador aprovados entre impressão/exportação, Contratos, Notas e Compras. Inclui download real do CSV, restauração após impressão, cabeçalhos agrupados, máscaras, exclusão de controles e isolamento da segunda página. Nenhuma alteração de banco/schema ou dependência adicional.


## Cadastro de usuários e perfil no cabeçalho

Meu perfil saiu da navegação lateral, inclusive do antigo atalho Minha conta. O botão do usuário no canto superior direito abre Meu perfil e Alterar senha; usa o avatar já validado pelo perfil e iniciais como alternativa. O endpoint de sessão `/clientes/api/auth/me/` inclui apenas a URL do próprio avatar. Salvar ou remover a foto atualiza o cabeçalho pelo refresh da sessão; recarregar preserva a foto. O acesso ao próprio perfil continua disponível sem empresa e sem permissões de módulos, em desktop e celular.

A navegação lateral inclui **Cadastro de usuário** (`/clientes/app/usuarios`) para quem possui `usuario.view_usuario` ou `usuario.add_usuario`; o botão Novo usuário exige a segunda permissão. A API `/usuario/api/usuarios/` oferece GET paginado/busca e POST; `/opcoes/` fornece empresas e permissões autorizadas. A antiga rota `/usuario/list/` aponta para a nova página. Não há edição, exclusão ou elevação de privilégios por esta API. Administradores podem autorizar responsáveis pela permissão de cadastro no Django Admin; nenhuma permissão de conta real foi concedida automaticamente.

A empresa ativa precisa pertencer ao responsável. A nova conta precisa de pelo menos uma empresa, e todas devem pertencer ao escopo do responsável. A lista mostra somente contas comuns ligadas à empresa ativa, excluindo staff/superusuários e contas com qualquer empresa fora do escopo. A seleção de módulos permite somente operações CRUD de negócio que o responsável já possui, excluindo criação de empresas, gestão de usuários, grupos e privilégios administrativos. As permissões selecionadas valem para todas as empresas vinculadas; a restrição por UF do responsável é herdada. Sem permissões de módulos, a nova conta acessa somente o próprio perfil.

A senha inicial exige confirmação e os validadores Django, incluindo 12 caracteres, e é armazenada por `set_password`. Usuário/e-mail são conferidos sem distinção de maiúsculas/minúsculas. A criação usa transação, bloqueio do responsável, locks PostgreSQL das identidades e auditoria sem senha/hash; falha de auditoria reverte o cadastro. Campos não autorizados são rejeitados. Respostas usam `no-store` e o cadastro tem limite próprio de 30 requisições/minuto por usuário, independente do perfil. Nenhuma migration, alteração de senha ou vínculo de usuário real foi necessária.

Validação desta etapa: 32 testes backend de Usuários (12 novos de cadastro e 20 de perfil/recuperação), seis de autenticação de Clientes e nove do Core; 21 testes frontend e build TypeScript/Vite aprovados. Nove cenários Playwright aprovados entre cadastro/avatar, perfil/recuperação e navegação. O cenário de cadastro efetivamente entra com a nova conta e confere a empresa disponível e a ausência do menu de gestão de usuários. Imagens e contas são sintéticas, em armazenamento temporário e PostgreSQL de testes isolado; capturas em `/tmp/gestao-users-e2e/`.


## Confirmação centralizada de exclusão

Os botões Excluir dos CRUDs de Clientes/Parceiros/Bloqueios/Liberações, Contratos, Notas, Compras, Bancos/Contas/Movimentos/Transferências, Financeiro, Contábil, Contatos, Serviços, Chaves, Empresas e Recadastramento usam `components/DeleteConfirmation.tsx`. O componente abre `App.useApp().modal.confirm` centralizado, com o nome/número do registro e os avisos específicos de vínculos.

Excluir recebe destaque de ação destrutiva e Cancelar recebe o foco inicial. Clicar fora mantém a confirmação aberta; Cancelar ou Escape fecha sem enviar DELETE. Cliques repetidos não criam diálogos duplicados. O componente aguarda a operação assíncrona e destrói a confirmação quando o registro/tela é desmontado, preservando o contexto da empresa. As regras de permissão e as proteções contra exclusão de registros vinculados continuam aplicadas pela API.

Validação: build TypeScript/Vite, 21 testes frontend e oito cenários Playwright de Clientes, Contas, Contratos e Financeiro aprovados. A posição central foi medida no viewport em desktop e celular após a animação; os testes verificam foco em Cancelar, clique fora, Escape, ausência de DELETE ao cancelar e preservação dos bloqueios por vínculos. Capturas em `/tmp/gestao-clientes-e2e/excluir-centralizado.png` e `excluir-centralizado-mobile.png`. Somente dados sintéticos no banco isolado de testes; nenhum cadastro real excluído.


## Pendências de produção — auditoria de 10/11/2026

Implementados hosts explícitos no ambiente local, perfil `layCliente.production` com DEBUG falso, HTTPS/cookies seguros/HSTS inicial, validação de domínio/segredo e bloqueio do login administrativo do banco. `DJANGO_ENV_FILE` seleciona o arquivo privado sem editar o ambiente local. Modelos de Nginx/systemd e instruções de ativação em `deploy/README.md`. O serviço não foi instalado nem iniciado: faltam domínio/DNS/certificado HTTPS reais e configuração SMTP. O perfil, validado com origem de teste, mantém somente os avisos W005/W021 por não ativar HSTS em subdomínios/preload antes de verificar o domínio.

Os aliases JWT receberam limites por IP e no-store. O limite de login é compartilhado com o React e não pode ser contornado com X-Forwarded-For arbitrário. O proxy confiável tem identificação explícita; o modelo Nginx sobrescreve cabeçalhos e aplica limite inclusive no login administrativo. Foram incluídos comandos `verificar_operacao` (somente leitura, SMTP opcional sem envio) e `preparar_rotacao` (candidatos privados, sem ativação).

A auditoria real somente de leitura foi salva em `.private/operacao/auditoria-20261110.json`, modo 0600: 9 grupos de clientes com identidade ambígua, 41 períodos com múltiplas liberações e 491 liberações com códigos diferentes do cadastro atual. As diferenças históricas exigem conciliação e não foram tratadas como autorização para exclusão/reescrita. A configuração fiscal possui dependências disponíveis, mas o certificado está ausente. Não houve emissão, envio de e-mail, mudança de empresa/código/liberação ou ativação de chaves novas. Candidatos de rotação estão em arquivo privado, sem valores expostos nesta documentação.

Validação: 82 testes backend aprovados entre segurança, Core, autenticação, Usuários, integrações e configuração fiscal; verificação do Gunicorn e checks Django aprovados com as duas ressalvas HSTS descritas. A rotação efetiva exige atualizar os consumidores e preservar/recifrar as credenciais fiscais antes de retirar fallbacks. A conclusão operacional ainda depende das informações e credenciais externas solicitadas ao responsável.
