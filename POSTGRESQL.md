# PostgreSQL: operação e correções de integração

## Ambiente local validado

Banco: `gestao_financeira_teste`, PostgreSQL 18.6. Este trabalho não selecionou nem alterou um ambiente de produção.

A conexão normal lê `DATABASE_URL` do `.env` e usa `gestao_financeira_app`, sem SUPERUSER, CREATEDB, CREATEROLE ou CREATE no schema public. Tem permissões de leitura/escrita sobre as tabelas da aplicação e uso das sequências/funções; o histórico `django_migrations` é somente leitura. Isso não equivale a isolamento por empresa no PostgreSQL: o acesso por empresa continua responsabilidade do código de aplicação, não de RLS.

A URL administrativa está em `DATABASE_ADMIN_URL`. URLs e senhas não devem ser copiadas para documentação, logs ou Git. O `.env` local tem permissão 0600. Reiniciar processos Django já em execução para que carreguem a conexão nova.

Migrations e manutenção administrativa:

```bash
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py migrate
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py repair_pg_sequences --apply
```

Auditoria de sequências, sem gravar:

```bash
.venv/bin/python manage.py repair_pg_sequences
```

O comando corrige somente sequências cujo próximo ID poderia colidir com registros existentes. Nunca reduz uma sequência. Usa locks de tabela com timeout e `ALTER SEQUENCE RESTART`, em transação. Aplicar em janela sem gravações concorrentes; novas importações com IDs explícitos exigem repetir a auditoria.

## Correções aplicadas

- `financeiro.0030_postgresql_financial_functions`: versiona as funções no histórico Django; possui dependências explícitas das tabelas utilizadas.
- `fechamento(date,date,integer,integer)`: usa datas inclusivas recebidas, incluindo anos atuais; grava empresa; verifica associação usuário/empresa e conta; transporta saldo e movimentos sem fechamento; usa lock por conta e transação; repetir o mesmo intervalo não duplica registros. Períodos limitados a 3661 dias. Registros existentes não são recalculados.
- Um fechamento anterior a outro já registrado é recusado: reabrir/reconciliar os posteriores primeiro. Vínculos conflitantes de empresa na conta são recusados para evitar fechar dados inconsistentes. Movimentos legados sem empresa são associados pela conta, sem reescrever o histórico.
- `fn_analise(date,date,integer)`: filtra por empresa nas cinco origens da consulta. A assinatura antiga sem empresa agora falha explicitamente; não retorna uma consolidação de empresas. A aplicação verifica o vínculo do usuário antes de consultar.
- Chamadas SQL parametrizadas e fechamento sob `transaction.atomic()`, sem BEGIN/COMMIT manuais na view.
- Totais mensais inicializados em zero e somados para todos os grupos, inclusive relatórios vazios.
- Datas dos formulários de análise/fechamento são obrigatórias e a ordem é validada. Esses formulários permanecem no app financeiro enquanto a migração React continua limitada ao app clientes.
- Sequências corrigidas: `clientes_uf`, `contratos_contrato`, `configambiente_ambiente`, `empresa_empresa`.

## Backup e reversão

Backup completo anterior às alterações locais:

`.backups/gestao_financeira_teste_20261030T183621Z.dump`

Arquivo em formato custom do pg_dump, cerca de 23 MB, permissão 0600. O catálogo foi lido por pg_restore; restauração integral desse backup ainda não foi ensaiada. O diretório fica fora do Git. Guardar uma cópia externa conforme a política de backup do ambiente; não depender apenas do disco local.

A migration 0030 possui reversão que restaura as definições do dump legado. Reverter também as chamadas no código junto com a migration, pois a assinatura de análise muda. A reversão reintroduz as limitações anteriores. Não reduzir sequências depois de novas inserções.

O script `scripts/configure_postgres.py --database gestao_financeira_teste --apply` automatiza backup, migrations, sequências, grants e troca do `.env`. Reutiliza o login somente quando já consta da configuração esperada; não assume controle de um login existente desconhecido. Deve rodar com acesso administrativo. Grants futuros são definidos para objetos criados pelo mesmo administrador; se o responsável por executar migrations mudar, revisar os default privileges.

## Testes e evidências

```bash
DATABASE_USE_ADMIN=1 .venv/bin/python manage.py test financeiro.test_postgresql clientes.tests \
  --settings=financeiro.pg_test_settings --keepdb
```

Usa `test_gestao_integracao_pg`, separado do banco local e criado a partir das migrations reais. `--keepdb` permite reaproveitar esse banco de testes; omitir a opção para limpeza automática ao final da execução normal. A conta administrativa precisa de CREATEDB para o runner.

23 testes passaram no PostgreSQL: autenticação JWT, escopo de clientes e parceiros, regras de cadastro e bloqueios, exclusões protegidas, fechamento em 2026, saldo anterior, idempotência, rollback, autorização da conta, análise prevista/realizada por empresa, relatório vazio e reparo das sequências.

Após aplicar, uma nova conexão confirmou login restrito, nenhuma migration pendente, nenhuma sequência atrasada, `manage.py check` sem problemas e GET autenticado da API de clientes com HTTP 200. Também houve teste transacional de INSERT/UPDATE/DELETE com o login restrito, sem deixar registro de teste.

Contagens preservadas: 808 clientes, 805 contratos, 30.281 notas, 34.255 receitas, 21.492 despesas, 14 usuários e 2 empresas. Isso não substitui conciliação contábil do histórico ou teste de todos os módulos do sistema.
