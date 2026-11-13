import { Table } from '../components/DataTable';
import { PrintHeader, PrintFooter, printSheet } from '../components/PrintLayout';
import { Alert, App, Button, Card, DatePicker, Empty, Form, Select, Space, } from 'antd';
import { DownloadOutlined, PrinterOutlined } from '@ant-design/icons';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import dayjs from 'dayjs';
import { api, errorMessage } from '../api';
import { useSession } from '../session';
import type { Page, Row } from '../types';
import { RemoteSelect } from '../components/RemoteSelect';
interface ReportValues { type: string; cliente?: number; parceiro?: number; uf?: number; competencia?: string; ativo?: string; dt_inicial?: string; dt_final?: string }
function reportRows(rows: Row[], kind: string): Record<string, unknown>[] {
  return rows.flatMap<Record<string, unknown>>(row => {
    if (kind.startsWith('NF_')) return [{ Nota: row.numero, Cliente: row.cliente_nome, CNPJ: row.cliente_cnpj, Competência: `${row.competencia}/${row.exercicio}`, Emissão: row.dt_data_emissao, Pagamento: row.dt_data_pagamento, 'Valor bruto': row.valor_bruto, ISS: row.imposto, 'Valor líquido': row.valor_liquido, Estado: row.estado_fiscal }];
    if (kind.startsWith('CON_')) {
      const base = { Contrato: row.numero, Cliente: row.cliente_nome, CNPJ: row.cliente_cnpj, UF: row.uf_nome,
        Início: row.dt_data_contrato, Fim: row.dt_data_final, 'Valor bruto': row.valor_bruto, 'Valor líquido': row.valor_liquido, Situação: row.ativo ? 'Ativo' : 'Inativo' };
      const items = row.itens as { produto_nome?: string | null; valor: string | null }[];
      return kind === 'CON_P' && items?.length ? items.map(item => ({ ...base, Produto: item.produto_nome, 'Valor do item': item.valor })) : [base];
    }
    const base = { Instituição: row.instituicao, CNPJ: row.cnpj, Responsável: row.resp_nome, Telefone: row.resp_telefone, Email: row.resp_email, Nascimento: row.dt_resp_nascimento };
    if (!['CP', 'CC'].includes(kind)) return [base];
    const contracts = row.contratos as { numero: string; valor_bruto: string; dt_data_contrato: string; dt_data_final: string; produtos: { sigla: string; valor: string }[] }[];
    return contracts?.length ? contracts.flatMap(c => {
      const fields = { ...base, Contrato: c.numero, Início: c.dt_data_contrato, Fim: c.dt_data_final, Valor: c.valor_bruto };
      return kind === 'CC' ? [fields] : c.produtos.map(p => ({ ...fields, Produto: p.sigla, 'Valor do produto': p.valor }));
    }) : [base];
  });
}
function csvValue(value: unknown) { let text = String(value ?? ''); if (/^[=+\-@\t\r]/.test(text)) text = "'" + text; return '"' + text.replace(/"/g, '""') + '"'; }
export function Reports() {
  const { empresa, can } = useSession();
  const { message } = App.useApp();
  const [params] = useSearchParams();
  const [form] = Form.useForm<ReportValues>();
  const kind = Form.useWatch('type', form) ?? params.get('tipo') ?? (can('clientes.view_cliente') ? 'CL' : can('contratos.view_contrato') ? 'CON_S' : 'NF_ALL');
  const contractReport = kind.startsWith('CON_'), noteReport = kind.startsWith('NF_');
  const [total, setTotal] = useState<string | null>(null);
  const [generatedKind, setGeneratedKind] = useState('');
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState(''), [loading, setLoading] = useState(false), [generated, setGenerated] = useState(false);
  const [title, setTitle] = useState(''), [printContext, setPrintContext] = useState('');
  const types = [...(can('clientes.view_cliente') ? [{ value: 'CL', label: 'Clientes' }, { value: 'CP', label: 'Clientes e produtos' }, { value: 'CC', label: 'Clientes e contratos' }, { value: 'NASC', label: 'Aniversariantes' }] : []), ...(can('clientes.view_parceiro') ? [{ value: 'PAR', label: 'Parceiros' }] : []), ...(can('contratos.view_contrato') ? [{ value: 'CON_S', label: 'Contratos — simplificado' }, { value: 'CON_P', label: 'Contratos e produtos' }] : []), ...(can('notas.view_nota') ? [{ value: 'NF_ALL', label: 'Notas fiscais' }, { value: 'NF_PAID', label: 'Notas fiscais pagas' }] : [])];
  async function generate(values: ReportValues) {
    setLoading(true); setError(''); setGenerated(false); setRows([]); setTotal(null);
    const isContract = values.type.startsWith('CON_'), isNote = values.type.startsWith('NF_');
    const path = values.type === 'PAR' ? 'parceiros/relatorio/' : values.type === 'NASC' ? 'clientes/aniversariantes/' : 'clientes/relatorio/';
    const query = new URLSearchParams({ page_size: '200' });
    if (values.type !== 'NASC') query.set('tipo_relatorio', isContract ? (values.type === 'CON_P' ? 'C' : 'S') : values.type);
    if (values.type === 'NF_PAID') query.set('pagas', 'true');
    if (values.competencia) query.set('competencia', values.competencia);
    if (values.cliente && values.type !== 'PAR') query.set('cliente', String(values.cliente));
    if (values.parceiro && values.type !== 'PAR') query.set('parceiro', String(values.parceiro));
    if (values.uf) query.set('uf', String(values.uf));
    if (isContract || isNote) for (const field of ['ativo', 'dt_inicial', 'dt_final'] as const) { if (values[field]) query.set(field, values[field]); }
    try {
      let next: string | null = (isNote ? '/notas/api/notas/relatorio/' : isContract ? '/contratos/api/contratos/relatorio/' : '/clientes/api/' + path) + '?' + query;
      const all: Row[] = [];
      while (next) {
        const page: Page<Row> & { valor_total?: string } = await api<Page<Row> & { valor_total?: string }>(next, {}, empresa);
        if (page.valor_total !== undefined) setTotal(page.valor_total);
        all.push(...page.results);
        if (page.next) { const url = new URL(page.next, location.origin); next = url.pathname + url.search; } else next = null;
      }
      setPrintContext([values.dt_inicial && values.dt_final ? `${isNote ? (values.type === 'NF_PAID' ? 'Pagamento' : 'Emissão') : 'Vencimento'}: ${dayjs(values.dt_inicial).format('DD/MM/YYYY')} a ${dayjs(values.dt_final).format('DD/MM/YYYY')}` : '', values.competencia ? `Mês: ${values.competencia}` : '', isContract ? (values.ativo === 'true' ? 'Contratos ativos' : values.ativo === 'false' ? 'Contratos inativos' : 'Todas as situações') : ''].filter(Boolean).join(' · '));
      setRows(reportRows(all, values.type)); setGeneratedKind(values.type); setGenerated(true); setTitle(types.find(t => t.value === values.type)?.label ?? 'Relatório');
    } catch (e) { setError(errorMessage(e)); } finally { setLoading(false); }
  }
  function download() {
    if (!rows.length) { void message.info('Nenhum registro para exportar.'); return; }
    const columns = Array.from(new Set(rows.flatMap(row => Object.keys(row))));
    const content = [columns.map(csvValue).join(';'), ...rows.map(row => columns.map(c => csvValue(row[c])).join(';'))].join('\r\n');
    const url = URL.createObjectURL(new Blob(['\uFEFF' + content], { type: 'text/csv;charset=utf-8;' }));
    const a = document.createElement('a'); a.href = url; a.download = generatedKind.startsWith('NF_') ? 'relatorio-notas.csv' : generatedKind.startsWith('CON_') ? 'relatorio-contratos.csv' : 'relatorio-clientes.csv'; a.click(); URL.revokeObjectURL(url);
  }
  const columns = Array.from(new Set(rows.flatMap(row => Object.keys(row)))).map(key => ({ title: key, dataIndex: key, render: (value: unknown) => String(value ?? '—') }));
  return <><div className="page-heading"><div><div className="eyebrow">RELACIONAMENTOS / RELATÓRIOS</div><h1>Informação para decidir.</h1><p>Consulte, exporte e compartilhe os dados da empresa selecionada.</p></div></div><Card className="report-controls"><Form form={form} initialValues={{ type: types.find(t => t.value === params.get('tipo'))?.value ?? types[0]?.value, ativo: 'true' }} layout="vertical" onFinish={generate}><Space align="start" wrap><Form.Item name="type" label="Relatório" rules={[{ required: true }]}><Select style={{ width: 230 }} options={types} /></Form.Item>{kind !== 'PAR' && <><div style={{ width: 260 }}><Form.Item name="cliente" label="Cliente"><RemoteSelect url={noteReport ? "/notas/api/notas/opcoes/?tipo=clientes" : contractReport ? "/contratos/api/contratos/opcoes/?tipo=clientes" : "/clientes/api/opcoes/?tipo=clientes"} /></Form.Item></div>{!noteReport && <div style={{ width: 240 }}><Form.Item name="parceiro" label="Parceiro"><RemoteSelect url={contractReport ? "/contratos/api/contratos/opcoes/?tipo=parceiros" : "/clientes/api/opcoes/?tipo=parceiros"} /></Form.Item></div>}</>}<div style={{ width: 120 }}><Form.Item name="uf" label="UF"><RemoteSelect url="/clientes/api/ufs/" labelField="sigla" /></Form.Item></div>{(contractReport || noteReport) && <>{!noteReport && <Form.Item name="ativo" label="Situação"><Select style={{ width: 130 }} allowClear placeholder="Todos" options={[{ value: 'true', label: 'Ativos' }, { value: 'false', label: 'Inativos' }]} /></Form.Item>}{[['dt_inicial', 'Vencimento inicial'], ['dt_final', 'Vencimento final']].map(([name, label]) => <Form.Item key={name} name={name} label={noteReport ? (kind === 'NF_PAID' ? label.replace('Vencimento', 'Pagamento') : label.replace('Vencimento', 'Emissão')) : label} getValueProps={value => ({ value: value ? dayjs(value) : null })} normalize={value => value?.format('YYYY-MM-DD') ?? undefined}><DatePicker format="DD/MM/YYYY" style={{ width: 160 }} /></Form.Item>)}</>}{kind === 'NASC' && <Form.Item name="competencia" label="Mês" rules={[{ required: true, message: 'Escolha o mês.' }]}><Select style={{ width: 130 }} options={Array.from({ length: 12 }, (_, i) => ({ value: String(i + 1), label: String(i + 1).padStart(2, '0') }))} /></Form.Item>}<Form.Item label=" "><Button aria-label="Gerar relatório" type="primary" htmlType="submit" loading={loading}>Gerar relatório</Button></Form.Item></Space></Form></Card>{error && <Alert type="error" title={error} showIcon />}{generated && <section className="table-panel report-output print-sheet print-landscape" id="print-general-report"><PrintHeader title={title} subtitle={[printContext, `${rows.length} linhas`].filter(Boolean).join(' · ')} reference="Relatórios" printOnly/><div className="table-toolbar print-hidden"><strong>{title} · {rows.length} linhas{total !== null && ' · Total líquido: ' + Number(total).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</strong><Space className="print-hidden"><Button icon={<DownloadOutlined />} onClick={download} disabled={!rows.length}>Exportar CSV</Button><Button icon={<PrinterOutlined />} aria-label="Imprimir" onClick={() => printSheet('print-general-report')} disabled={!rows.length}>Imprimir</Button></Space></div><Table dataSource={rows.map((r, i) => ({ ...r, key: i }))} columns={columns} pagination={false} scroll={{ x: 950 }} locale={{ emptyText: <Empty description="Nenhum registro para os filtros selecionados." /> }} />{total !== null && <div className="print-summary layout-print-only">Total líquido: <strong>{Number(total).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</strong></div>}<PrintFooter/></section>}</>;
}
