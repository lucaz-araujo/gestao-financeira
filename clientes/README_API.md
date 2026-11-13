# API de clientes — etapa de migração

`forms.py` foi removido. As views deste app respondem JSON via DRF e deixam de renderizar os templates antigos. As telas React 19 + TypeScript + Ant Design estão em `/clientes/app/`; instalação e execução em `frontend/README.md`.

## Autenticação e empresa

Enviar `Authorization: Bearer <access>` e `X-Empresa-ID: <id>` nas operações de clientes, parceiros, liberações e bloqueios. A empresa deve estar em `request.user.empresas`, inclusive para superusuários. Como alternativas, aceita-se `?empresa=<id>` ou a empresa da sessão Django, nessa ordem de prioridade após o header. Empresa ausente/inválida retorna 400; empresa não autorizada retorna 403. Registros de outras empresas ou fora da UF do usuário retornam 404 em operações por ID.

`empresa`, `usuario`, datas de auditoria e chave de liberação são definidos pelo servidor, não pelo payload. A API também aceita sessão Django para os apps ainda não migrados, com CSRF obrigatório nas escritas. JWT é verificado primeiro: um Bearer inválido não é substituído por uma sessão válida.

## Recursos

Prefixo: `/clientes/api/`.

| Recurso | Operações |
| --- | --- |
| `clientes/` | GET paginado, POST |
| `clientes/{id}/` | GET, PUT, PATCH, DELETE |
| `parceiros/` e `parceiros/{id}/` | Mesmo CRUD |
| `liberacoes/` | GET paginado, POST |
| `liberacoes/{id}/` | GET, DELETE |
| `liberacoes/{id}/atualizar_chave/` | POST, regenera chave com os códigos atuais do cliente |
| `bloqueios/` e `bloqueios/{id}/` | Mesmo CRUD de clientes |
| `ufs/`, `municipios/`, `municipios-br/` | GET paginado e GET por ID; somente referência |
| `clientes/relatorio/` | GET, `tipo_relatorio=CL`, `CP` ou `CC` |
| `clientes/aniversariantes/` | GET, `competencia=1..12` obrigatória |
| `parceiros/relatorio/` | GET |

Datas de entrada: ISO `YYYY-MM-DD`. Chaves estrangeiras: IDs numéricos. `senhatcm` é somente escrita; `token` interno do cliente não é exposto. Omissão da senha em PATCH preserva o valor atual.

Exemplo de criação em `POST /clientes/api/clientes/`:

```json
{
  "instituicao": "Cliente de exemplo",
  "cnpj": "11.222.333/0001-81",
  "endereco": "Rua A",
  "numero": "1",
  "bairro": "Centro",
  "cep": "60000-000",
  "uf": 1
}
```

O ID de UF deve existir. A API preserva os campos obrigatórios dos cadastros e valida CNPJ, CPF do responsável, município/UF, código de entidade e duplicidade Layout/entidade. CPF/CNPJ mantêm o validador numérico legado; este trabalho não altera o formato fiscal aceito pelo sistema. A validação de unicidade Layout/entidade continua na aplicação, sem introduzir uma constraint nova sobre dados existentes.

Liberações recebem `cliente`, `competencia` e `exercicio`. A competência é normalizada para dois dígitos e o ano não fica mais limitado às opções antigas 2016–2022. A chave mantém o protocolo das integrações existentes. Bloqueios recebem `cliente`, `dt_ate`, `dt_aparte` e os indicadores de liberação; ambas as datas são obrigatórias e a final não pode anteceder a inicial.

## Filtros e paginação

- Clientes: `search`, `cliente`, `parceiro`, `uf`, `ativo`, `desativar`.
- Parceiros: `search`, `uf`.
- Liberações/bloqueios: `cliente`, `parceiro`.
- Municípios: `uf` (ID), `search`; municípios-br: `uf` (sigla ou ID).
- Filtros por IDs aceitam valores repetidos ou separados por vírgula.
- Paginação: `page`, `page_size` (padrão 50, máximo 200).
- Resposta: `{ "count": 0, "next": null, "previous": null, "results": [] }`.
- Relatórios também são paginados. CP/CC acrescentam `contratos` ativos e seus produtos/valores, sempre dentro da empresa selecionada. A apresentação/impressão passa ao frontend.

## Permissões

CRUD de clientes/parceiros/bloqueios exige as permissões Django `view`, `add`, `change` e `delete` do respectivo modelo. Bloqueios agora usam as permissões de `clientes.liberacaodatas`, corrigindo o uso legado de permissões de outros cadastros; revisar grupos antes de disponibilizar a tela.

Listar, consultar e criar liberações preserva `financeiro.add_recreceita`. Regenerar chave exige `clientes.change_liberacao`; excluir exige `clientes.delete_liberacao`. Referências geográficas e CEP exigem usuário autenticado.

## Erros

- 400: campos inválidos, com erros por campo compatíveis com a apresentação no Ant Design.
- 401: sem autenticação ou JWT inválido/expirado; SimpleJWT inclui `code: "token_not_valid"` para token inválido.
- 403: sem permissão ou empresa não autorizada.
- 404: registro inexistente ou fora do escopo.
- 405: método não suportado.
- 409: vínculo protegido impede exclusão ou conflito de integridade na gravação.
- 502: falha no serviço externo de CEP.

A exclusão não tenta remover contratos, notas ou recebimentos do cliente. Relações PROTECT impedem a operação e mantêm os dependentes intactos.

## Transição das rotas antigas

Os nomes das rotas foram preservados para `reverse()` dos apps restantes. Listas/relatórios usam GET com query parameters; criação usa POST; edição aceita PUT/PATCH e POST legado; exclusão aceita DELETE e POST legado. O corpo retornado agora é JSON, sem `html_form`, `html_list` ou redirecionamento de login. A interface antiga de clientes não é compatível com esse novo contrato.

`cidade/<uf>` e `retorna_municipio/` preservam os formatos de opções utilizados por selects dos outros apps, com autenticação. `municipiobr/<uf>` foi corrigida para a view de consulta e o campo `ufmuni`. `retorna_cep/?logradouro=...` retorna `{ "results": [...] }`; o provedor legado de CEP foi mantido com timeout e não foi validado ao vivo.

## Verificação

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py test clientes.tests --settings=clientes.tests.settings
```

Os testes usam SQLite em memória, criando o schema diretamente dos modelos. Não acessam dados locais e não validam o histórico de migrations nem particularidades do PostgreSQL. Os métodos adicionados aos modelos não modificam o schema.
