export interface ContractItem { id?: number; produtos: number; produto_nome?: string | null; valor: string | null }
export interface Renewal { id?: number; dt_data_inicio: string; dt_data_final: string }
export interface ContractNote { id: number; numero: string | null; competencia: number; exercicio: number; dt_data_emissao: string; dt_data_vencimento: string | null; dt_data_pagamento: string | null; valor_liquido: string | null }
export interface Contract {
  id: number; empresa: number; cliente: number; cliente_nome: string; cliente_cnpj: string | null; uf_nome: string | null;
  numero: string | null; dia_nota: number | null; exercicio: number | null; dt_data_contrato: string | null; dt_data_final: string | null;
  objeto: string | null; observacoes: string | null; valor_bruto: string | null; perc_iss: string | null; perc_irpj: string | null;
  valor_iss: string | null; valor_irpj: string | null; valor_liquido: string | null;
  ativo: boolean; emitirnota: boolean; prestacao_municipio: boolean; tem_nota: boolean;
  itens: ContractItem[]; renovacoes: Renewal[]; notas: ContractNote[];
}
export const money = (value: unknown) => value == null || value === '' ? '—' : Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
