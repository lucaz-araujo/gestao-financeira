import { describe, expect, it } from 'vitest';
import { readTable, tableCsv } from '../src/utils/tableExport';
function table(html: string) { const node = document.createElement('table'); node.innerHTML = html; return node; }
describe('exportação das tabelas', () => {
  it('exporta dados apresentados, preserva máscaras e omite botões e ações', () => {
    const result = readTable(table('<thead><tr><th>Cliente</th><th>Chave</th><th>Ações</th></tr></thead><tbody><tr><td><button class="record-title">João</button></td><td>12345678…<button>Copiar segredo</button></td><td><button>Excluir</button></td></tr></tbody>'));
    expect(result).toEqual({ headers: ['Cliente', 'Chave'], rows: [['João', '12345678…']] });
  });
  it('combina cabeçalhos agrupados sem deslocar colunas com rowspan', () => {
    const result = readTable(table('<thead><tr><th rowspan="2">Centro</th><th colspan="2">JAN</th></tr><tr><th>Previsto</th><th>Realizado</th></tr></thead><tbody><tr><td>A</td><td>R$ 1,00</td><td>R$ 2,00</td></tr></tbody>'));
    expect(result.headers).toEqual(['Centro', 'JAN / Previsto', 'JAN / Realizado']);
    expect(result.rows[0]).toEqual(['A', 'R$ 1,00', 'R$ 2,00']);
  });
  it('ignora linhas técnicas, ausência de dados e controles de conciliação', () => {
    expect(readTable(table('<thead><tr><th>Valor</th><th>Vincular receita</th><th>Ação</th></tr></thead><tbody><tr class="ant-table-measure-row"><td>medição</td></tr><tr><td>100,00</td><td><input value="segredo"></td><td>Estornar</td></tr><tr class="ant-table-placeholder"><td colspan="3">Vazio</td></tr></tbody>'))).toEqual({ headers: ['Valor'], rows: [['100,00']] });
  });
  it('gera CSV UTF-8 com acentos, separadores e proteção contra fórmulas', () => {
    const result = tableCsv({ headers: ['Descrição'], rows: [['João; "Teste"'], [' =HYPERLINK("url")'], ['@SUM(1)'], ['000123']] });
    expect(result).toBe('\uFEFF"Descrição"\r\n"João; ""Teste"""\r\n"\' =HYPERLINK(""url"")"\r\n"\'@SUM(1)"\r\n"000123"');
  });
});
