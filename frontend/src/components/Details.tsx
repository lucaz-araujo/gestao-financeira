import { Descriptions, Drawer, Tag, Typography } from 'antd';
import dayjs from 'dayjs';
import type { Resource, Row } from '../types';
const labels: Record<string, string> = {
  descricao: 'Descrição', sigla: 'Sigla', tipo_produto: 'Tipo', valor: 'Valor',
  instituicao: 'Instituição', cnpj: 'CNPJ', tipo_pessoa: 'Tipo de pessoa', gcf: 'Inscrição estadual / CGF',
  endereco: 'Endereço', numero: 'Número', bairro: 'Bairro', cidade_nome: 'Município', uf_nome: 'UF', cep: 'CEP', site: 'Site',
  parceiro_nome: 'Parceiro', resp_nome: 'Responsável', resp_cargo: 'Cargo', resp_cpf: 'CPF do responsável',
  dt_resp_nascimento: 'Nascimento', resp_telefone: 'Telefone', resp_email: 'E-mail',
  codigolayout: 'Código Layout', codigoentidade: 'Código da entidade', codigosim: 'Código SIM', codigoold: 'Código antigo',
  codigotcm: 'Código TCM', usertcm: 'Usuário TCM', banco_nome: 'Banco', agencia: 'Agência', numero_conta: 'Número da conta',
  ativo: 'Ativo', desativar: 'Desativado', observacoes: 'Observações', libera_tcm: 'TCM liberado',
  libera_pagonline: 'Pagamento online liberado', libera_sistema: 'Sistema liberado', libera_transparencia: 'Transparência liberada',
  libera_contracheque: 'Contracheque liberado', gerar_notas: 'Geração de notas', excecao: 'Exceção nas liberações',
  libera_clientes: 'Libera clientes', dt_data_limite: 'Data limite', cliente_nome: 'Cliente', competencia: 'Competência',
  exercicio: 'Exercício', dt_liberacao: 'Liberado em', chave: 'Chave de liberação', codigo: 'Código da entidade',
  codigo_layout: 'Código Layout', usuario_nome: 'Registrado por', dt_ate: 'Data inicial', dt_aparte: 'Data final',
};
export function Details({ resource, row, onClose }: { resource: Resource; row: Row | null; onClose: () => void }) {
  function display(field: string, value: unknown) {
    if (typeof value === 'boolean') return <Tag color={value ? 'red' : 'default'}>{value ? 'Sim' : 'Não'}</Tag>;
    if (value == null || value === '') return '—';
    if (field.startsWith('dt_')) return dayjs(String(value)).format(field === 'dt_liberacao' ? 'DD/MM/YYYY HH:mm' : 'DD/MM/YYYY');
    if (field === 'tipo_produto') return value === 'S' ? 'Serviço' : 'Produto';
    if (field === 'valor') return Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    if (field === 'chave') return <Typography.Text copyable style={{ wordBreak: 'break-all' }}>{String(value)}</Typography.Text>;
    return String(value);
  }
  return <Drawer title={row?.instituicao || row?.descricao || (resource === 'liberacoes' ? 'Detalhes da liberação' : 'Detalhes do bloqueio')} open={!!row} onClose={onClose} size={700}><Descriptions bordered column={1} size="small" items={row ? Object.entries(labels).filter(([field]) => field in row).map(([field, label]) => ({ key: field, label, children: display(field, row[field]) })) : []} /></Drawer>;
}
