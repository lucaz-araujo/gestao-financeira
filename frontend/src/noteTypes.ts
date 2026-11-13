export interface Note {
  id: number; contrato: number; contrato_numero: string; cliente_nome: string; cliente_cnpj: string;
  numero: string | null; competencia: number; exercicio: number; dt_data_emissao: string; dt_data_vencimento: string | null;
  valor_bruto: string; imposto: string; aliq_imposto: string; valor_liquido: string; texto_nota: string;
  estado_fiscal: string; tem_financeiro: boolean; tem_operacoes: boolean; ja_enviou: boolean;
  protocolo_envio: string | null; protocolo_recebimento: string | null; numero_rps: number | null; numero_lote: number | null;
  cidade: number | null; uf: number | null; cidade_nome: string | null; uf_nome: string | null; cancelada_em: string | null;
}
export interface Operation { id: string; acao: string; estado: string; criada_em: string; usuario_nome: string; resultado: { detail?: string; mensagens?: { codigo: string; mensagem: string; correcao: string }[]; [key: string]: unknown } }
export interface FiscalConfig { disponivel: boolean; homologacao: boolean | null; pendencias: string[]; email_disponivel: boolean }
export const noteEndpoint = '/notas/api/notas/';
export const noteStates = [{ value: 'rascunho', label: 'Rascunho' }, { value: 'enviada', label: 'Enviada' }, { value: 'autorizada', label: 'Autorizada' }, { value: 'cancelada', label: 'Cancelada' }, { value: 'incerta', label: 'Resultado incerto' }, { value: 'processando', label: 'Em processamento' }];
export function stateLabel(state: string) { return noteStates.find(s => s.value === state)?.label ?? state; }
