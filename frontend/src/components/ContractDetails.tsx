import { Table } from './DataTable';
import { PrintHeader, PrintFooter, printSheet } from './PrintLayout';
import { Button, Descriptions, Drawer, Space, Tag, Typography } from 'antd';
import { PrinterOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import type { Contract } from '../contractTypes';
import { money } from '../contractTypes';
const date = (value: unknown) => value ? dayjs(String(value)).format('DD/MM/YYYY') : '—';
export function ContractDetails({ value, close }: { value: Contract | null; close: () => void }) {
  return <Drawer rootClassName="contract-details" open={!!value} onClose={close} title="Detalhes do contrato" size={900} extra={<Button aria-label="Imprimir contrato" icon={<PrinterOutlined />} onClick={() => printSheet('print-contract')}>Imprimir</Button>}>
    {value && <article className="contract-printable print-sheet" id="print-contract">
      <PrintHeader title={`Resumo do contrato ${value.numero ?? ''}`} reference="Contratos"/>
      <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small" items={[
        { key: 'cliente', label: 'Cliente', children: value.cliente_nome }, { key: 'cnpj', label: 'CNPJ', children: value.cliente_cnpj || '—' },
        { key: 'inicio', label: 'Data do contrato', children: date(value.dt_data_contrato) }, { key: 'fim', label: 'Data final', children: date(value.dt_data_final) },
        { key: 'ano', label: 'Exercício', children: value.exercicio }, { key: 'dia', label: 'Dia da nota', children: value.dia_nota },
        { key: 'ativo', label: 'Situação', children: <Tag color={value.ativo ? 'red' : 'default'}>{value.ativo ? 'Ativo' : 'Inativo'}</Tag> },
        { key: 'emissao', label: 'Emitir nota', children: value.emitirnota ? 'Sim' : 'Não' },
        { key: 'local', label: 'Serviço no município', children: value.prestacao_municipio ? 'Sim' : 'Não' },
        { key: 'objeto', label: 'Objeto', children: value.objeto || '—', span: 2 }, { key: 'obs', label: 'Observações', children: value.observacoes || '—', span: 2 },
      ]} />
      <Typography.Title level={5}>Financeiro</Typography.Title>
      <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small" items={[
        { key: 'bruto', label: 'Valor bruto', children: money(value.valor_bruto) }, { key: 'liquido', label: 'Valor líquido', children: money(value.valor_liquido) },
        { key: 'iss', label: 'ISS', children: `${money(value.valor_iss)} (${value.perc_iss ?? '—'}%)` }, { key: 'irpj', label: 'IRPJ', children: `${money(value.valor_irpj)} (${value.perc_irpj ?? '—'}%)` },
      ]} />
      <Typography.Title level={5}>Produtos e serviços</Typography.Title>
      <Table rowKey="id" size="small" pagination={false} dataSource={value.itens} columns={[{ title: 'Produto', dataIndex: 'produto_nome', render: name => name || 'Produto não disponível' }, { title: 'Valor', dataIndex: 'valor', render: value => value == null ? '—' : Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 2, maximumFractionDigits: 5 }) }]} />
      <Typography.Title level={5}>Renovações</Typography.Title>
      <Table rowKey="id" size="small" pagination={false} dataSource={value.renovacoes} columns={[{ title: 'Início', dataIndex: 'dt_data_inicio', render: date }, { title: 'Fim', dataIndex: 'dt_data_final', render: date }]} />
      <Typography.Title level={5}>Notas vinculadas</Typography.Title>
      <Table rowKey="id" size="small" pagination={false} scroll={{ x: 540 }} dataSource={value.notas} columns={[
        { title: 'Número', dataIndex: 'numero', render: number => number || 'Sem número' }, { title: 'Competência', render: (_, note) => `${String(note.competencia).padStart(2, '0')}/${note.exercicio}` },
        { title: 'Emissão', dataIndex: 'dt_data_emissao', render: date }, { title: 'Vencimento', dataIndex: 'dt_data_vencimento', render: date },
        { title: 'Pagamento', dataIndex: 'dt_data_pagamento', render: date }, { title: 'Valor', dataIndex: 'valor_liquido', render: money },
      ]} />
      <PrintFooter/>
    </article>}
  </Drawer>;
}
