import { DeleteConfirmation } from '../components/DeleteConfirmation';
import { Table } from '../components/DataTable';
import { PrintHeader, PrintFooter, printSheet } from '../components/PrintLayout';
import { Alert, App, Button, Col, DatePicker, Descriptions, Drawer, Empty, Form, Input, InputNumber, Modal, Row, Select, Space, Tag } from 'antd';
import { DeleteOutlined, DownloadOutlined, EditOutlined, EyeOutlined, PlusOutlined, PrinterOutlined, ReloadOutlined } from '@ant-design/icons';
import { useEffect, useRef, useState, type ComponentProps } from 'react';
import { useSearchParams } from 'react-router-dom';
import dayjs from 'dayjs';
import { api, ApiError, errorMessage } from '../api';
import { useSession } from '../session';
import type { Page, Row as RecordRow } from '../types';
import { RemoteSelect } from '../components/RemoteSelect';
export type BankResource = 'bancos' | 'contas' | 'movimentos' | 'transferencias';
const base = '/conta/api/';
const configs = {
  bancos: { title: 'Bancos', single: 'banco', model: 'banco', description: 'Catálogo de instituições bancárias compartilhado entre as empresas.' },
  contas: { title: 'Contas bancárias', single: 'conta', model: 'conta', description: 'Dados bancários e vínculo contábil das contas da empresa.' },
  movimentos: { title: 'Movimentações', single: 'movimento', model: 'movimento', description: 'Créditos, débitos e histórico de movimentação das contas.' },
  transferencias: { title: 'Transferências', single: 'transferência', model: 'transferencia', description: 'Registre a saída e a entrada entre contas da empresa.' },
};
const consistencyOptions = [{ value: 'consistente', label: 'Movimentos consistentes' }, { value: 'pendente', label: 'Conciliação necessária' }];
const documents = [{ value: 'TED', label: 'TED' }, { value: 'DOC', label: 'DOC' }, { value: 'CHE', label: 'Cheque' }, { value: 'TAR', label: 'Tarifa' }, { value: 'OUT', label: 'Outros' }, { value: 'DEP', label: 'Depósito' }];
const money = (v: unknown) => v == null ? '—' : Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 3, maximumFractionDigits: 3 });
const required = [{ required: true, message: 'Preencha este campo.' }];
const text = (value: unknown) => value == null || value === '' ? '—' : String(value);
interface BankRow extends RecordRow { editavel?: boolean; valor?: string | null }
interface Report extends Page<BankRow> { creditos?: string; debitos?: string; saldo_periodo?: string; saldo_anterior?: string; saldo_final?: string; valor_total?: string }
function DateInput({ name, label }: { name: string; label: string }) {
  return <Form.Item name={name} label={label} rules={required} getValueProps={v => ({ value: v ? dayjs(v) : null })} normalize={v => v?.format('YYYY-MM-DD') ?? null}><DatePicker format="DD/MM/YYYY" style={{ width: '100%' }} /></Form.Item>;
}
function AccountSelect({ type = 'contas', ...props }: Omit<ComponentProps<typeof RemoteSelect>, 'url'> & { type?: string }) { return <RemoteSelect {...props} url={base + 'opcoes/?tipo=' + type} labelField="descricao" />; }
function BankingForm({ resource }: { resource: BankResource }) {
  if (resource === 'bancos') return <><Form.Item name="codigo" label="Código do banco" rules={required}><Input maxLength={8} /></Form.Item><Form.Item name="nome" label="Nome do banco" rules={required}><Input maxLength={10} /></Form.Item></>;
  if (resource === 'contas') return <>
    <Form.Item name="descricao" label="Descrição da conta" rules={required}><Input maxLength={30} /></Form.Item>
    <Form.Item name="banco" label="Banco" rules={required}><AccountSelect type="bancos" /></Form.Item>
    <Row gutter={16}>{[['agencia', 'Agência', 10], ['dv_agencia', 'Dígito da agência', 1], ['numeroconta', 'Número da conta', 12], ['dv_conta', 'Dígito da conta', 1]].map(([name, label, max]) => <Col span={12} key={name}><Form.Item name={String(name)} label={label} rules={name === 'dv_conta' ? [] : required}><Input maxLength={Number(max)} /></Form.Item></Col>)}</Row>
    <Form.Item name="conta_contabil" label="Plano de contas"><AccountSelect type="planos" /></Form.Item>
  </>;
  return <>
    {resource === 'movimentos' ? <><Form.Item name="conta" label="Conta bancária" rules={required}><AccountSelect /></Form.Item><Row gutter={16}><Col span={12}><Form.Item name="tipo_movimento" label="Crédito ou débito" rules={required}><Select options={[{ value: 'C', label: 'Crédito' }, { value: 'D', label: 'Débito' }]} /></Form.Item></Col><Col span={12}><Form.Item name="tipo_documento" label="Tipo de documento" rules={required}><Select options={documents} /></Form.Item></Col></Row></> : <><p>Este lançamento registra um débito na origem e um crédito no destino. Não executa uma operação no banco.</p><Form.Item name="conta_origem" label="Conta de origem" rules={required}><AccountSelect /></Form.Item><Form.Item name="conta_destino" label="Conta de destino" rules={required}><AccountSelect /></Form.Item></>}
    <Row gutter={16}><Col span={12}><DateInput name="dt_movimento" label="Data do movimento" /></Col><Col span={12}><Form.Item name="valor" label="Valor" rules={required}><InputNumber<string> stringMode min="0.001" max="999999999999.999" precision={3} decimalSeparator="," prefix="R$" style={{ width: '100%' }} /></Form.Item></Col></Row>
    <Form.Item name="nr_documento" label="Número do documento"><Input maxLength={20} /></Form.Item><Form.Item name="historico" label="Histórico"><Input.TextArea rows={3} maxLength={resource === 'movimentos' ? 560 : 260} /></Form.Item>
  </>;
}
export function Banking({ resource }: { resource: BankResource }) {
  const createLabel = resource === 'contas' ? 'Nova conta' : resource === 'transferencias' ? 'Nova transferência' : 'Novo ' + configs[resource].single;
  const config = configs[resource], endpoint = base + resource + '/', financial = resource === 'movimentos' || resource === 'transferencias';
  const { empresa, can } = useSession(); const { message } = App.useApp();
  const [params, setParams] = useSearchParams();
  const [form] = Form.useForm(), [reportForm] = Form.useForm();
  const reportKind = Form.useWatch('kind', reportForm);
  const [data, setData] = useState<Page<BankRow>>({ count: 0, results: [], next: null, previous: null });
  const [search, setSearch] = useState(''), [page, setPage] = useState(1), [reload, setReload] = useState(0);
  const [filter, setFilter] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false), [error, setError] = useState('');
  const [editor, setEditor] = useState<BankRow | 'new' | null>(null), [detail, setDetail] = useState<BankRow | null>(null);
  const [saving, setSaving] = useState(false), [saveError, setSaveError] = useState('');
  const [reportOpen, setReportOpen] = useState(false), [reportLoading, setReportLoading] = useState(false), [reportError, setReportError] = useState('');
  const [report, setReport] = useState<Report | null>(null), [reportTitle, setReportTitle] = useState(''), [printPeriod, setPrintPeriod] = useState('');
  const generation = useRef(0);
  useEffect(() => () => { generation.current++; }, []);
  useEffect(() => { if (params.has('relatorio') && financial) { reportForm.setFieldValue('kind', params.get('relatorio')); setReportOpen(true); } }, [params, financial, reportForm]);
  useEffect(() => {
    let alive = true; const controller = new AbortController(); setLoading(true); setError('');
    const timer = setTimeout(() => {
      const query = new URLSearchParams({ search, page: String(page), page_size: '20', ...filter });
      api<Page<BankRow>>(endpoint + '?' + query, { signal: controller.signal }, empresa).then(value => { if (alive) setData(value); }).catch(e => { if (alive) setError(errorMessage(e)); }).finally(() => { if (alive) setLoading(false); });
    }, search ? 250 : 0);
    return () => { alive = false; clearTimeout(timer); controller.abort(); };
  }, [endpoint, empresa, page, search, filter, reload]);
  useEffect(() => {
    if (editor) { form.resetFields(); form.setFieldsValue(editor === 'new' ? { dt_movimento: dayjs().format('YYYY-MM-DD'), valor: '0.001', tipo_movimento: 'C', tipo_documento: 'OUT' } : editor); }
  }, [editor, form]);
  async function edit(row: BankRow | 'new') {
    setSaveError('');
    if (row === 'new') { generation.current++; setEditor('new'); return; }
    const token = ++generation.current;
    try { const value = await api<BankRow>(endpoint + row.id + '/', {}, empresa); if (token === generation.current) setEditor(value); }
    catch (e) { void message.error(errorMessage(e)); }
  }
  async function save(values: Record<string, unknown>) {
    if (!editor) return; const token = generation.current; setSaving(true); setSaveError('');
    try { await api(endpoint + (editor === 'new' ? '' : editor.id + '/'), { method: editor === 'new' ? 'POST' : 'PATCH', body: JSON.stringify(values) }, empresa); if (token === generation.current) { setEditor(null); setReload(v => v + 1); setReport(null); void message.success('Registro salvo.'); } }
    catch (e) { if (token === generation.current) { setSaveError(errorMessage(e)); if (e instanceof ApiError && e.status === 400) form.setFields(Object.entries(e.data).filter(([, errors]) => Array.isArray(errors)).map(([name, errors]) => ({ name, errors: errors as string[] }))); } }
    finally { if (token === generation.current) setSaving(false); }
  }
  async function remove(row: BankRow) {
    try { await api(endpoint + row.id + '/', { method: 'DELETE' }, empresa); setReport(null); if (data.results.length === 1 && page > 1) setPage(page - 1); else setReload(v => v + 1); void message.success('Registro excluído.'); }
    catch (e) { void message.error(errorMessage(e)); }
  }
  function updateFilter(name: string, value?: string) { setFilter(old => { const next = { ...old }; if (value) next[name] = value; else delete next[name]; return next; }); setPage(1); }
  async function generate(values: Record<string, string>) {
    setReportLoading(true); setReportError(''); setReport(null);
    const { kind, ...fields } = values;
    const query = new URLSearchParams({ page_size: '200' });
    for (const [key, value] of Object.entries(fields)) if (value != null && value !== '') query.set(key, String(value));
    if (kind === 'cheques') { query.set('tipo_documento', 'CHE'); query.set('tipo_movimento', 'D'); }
    try {
      let next: string | null = endpoint + (kind === 'extrato' ? 'extrato/' : 'relatorio/') + '?' + query;
      let first: Report | undefined; const rows: BankRow[] = [];
      while (next) {
        const result: Report = await api<Report>(next, {}, empresa);
        first ??= result; rows.push(...result.results);
        const url: URL | null = result.next ? new URL(result.next, location.origin) : null;
        next = url ? url.pathname + url.search : null;
      }
      if (first) setReport({ ...first, results: rows });
      setPrintPeriod(`Período de ${dayjs(values.dt_inicial).format('DD/MM/YYYY')} a ${dayjs(values.dt_final).format('DD/MM/YYYY')}`);
      setReportTitle(kind === 'extrato' ? 'Extrato da conta' : kind === 'cheques' ? 'Cheques emitidos' : resource === 'movimentos' ? 'Relatório de movimentações' : 'Relatório de transferências');
      setReportOpen(false); setParams({});
    } catch (e) { setReportError(errorMessage(e)); } finally { setReportLoading(false); }
  }
  const dateColumn = { title: 'Data', dataIndex: 'dt_movimento', render: (v: string) => dayjs(v).format('DD/MM/YYYY') };
  const columns = resource === 'bancos' ? [{ title: 'Código', dataIndex: 'codigo' }, { title: 'Banco', dataIndex: 'nome' }] : resource === 'contas' ? [
    { title: 'Descrição', dataIndex: 'descricao' }, { title: 'Banco', dataIndex: 'banco_nome' }, { title: 'Agência', render: (_: unknown, row: BankRow) => `${row.agencia}-${row.dv_agencia}` }, { title: 'Conta', render: (_: unknown, row: BankRow) => `${row.numeroconta}${row.dv_conta ? '-'+row.dv_conta : ''}` },
  ] : resource === 'movimentos' ? [dateColumn, { title: 'Conta', dataIndex: 'conta_nome' }, { title: 'Tipo', dataIndex: 'tipo_movimento', render: (v: string) => <Tag color={v === 'D' ? 'red' : 'default'}>{v === 'C' ? 'Crédito' : 'Débito'}</Tag> }, { title: 'Documento', dataIndex: 'nr_documento', render: text }, { title: 'Valor', dataIndex: 'valor', render: money }, { title: 'Origem', render: (_: unknown, row: BankRow) => row.transferencia ? `Transferência #${row.transferencia}` : row.receita ? 'Recebimento' : row.despesa ? 'Pagamento' : 'Manual' },
  ] : [dateColumn, { title: 'Origem', dataIndex: 'origem_nome' }, { title: 'Destino', dataIndex: 'destino_nome' }, { title: 'Documento', dataIndex: 'nr_documento', render: text }, { title: 'Valor', dataIndex: 'valor', render: money }, { title: 'Movimentos', render: (_: unknown, row: BankRow) => <Tag color={row.editavel === false ? 'red' : 'default'}>{row.editavel === false ? 'Conciliação necessária' : 'Consistentes'}</Tag> }];
  function csv() {
    if (!report?.results.length) return;
    const headers = resource === 'transferencias' ? ['Data', 'Origem', 'Destino', 'Documento', 'Valor', 'Histórico', 'Movimentos'] : ['Data', 'Conta', 'Tipo', 'Documento', 'Valor', 'Histórico'];
    const rows = report.results.map(r => [r.dt_movimento, ...(resource === 'transferencias' ? [r.origem_nome, r.destino_nome] : [r.conta_nome, r.tipo_movimento]), r.nr_documento, r.valor, r.historico, ...(resource === 'transferencias' ? [r.editavel === false ? 'Conciliação necessária' : 'Consistentes'] : [])]);
    const escape = (value: unknown) => { let valueText = String(value ?? ''); if (/^[=+\-@\t\r]/.test(valueText)) valueText = "'" + valueText; return '"'+valueText.replace(/"/g, '""')+'"'; };
    const blob = new Blob(['\uFEFF'+[headers, ...rows].map(row => row.map(escape).join(';')).join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'relatorio-'+resource+'.csv'; a.click(); URL.revokeObjectURL(url);
  }
  return <>
    <div className="page-heading"><div><div className="eyebrow">CONTAS / {config.title.toUpperCase()}</div><h1>{config.title}<span className="count-pill">{data.count}</span></h1><p>{config.description}</p></div><Space wrap>{financial && <Button onClick={() => { setReportError(''); setReportOpen(true); }}>Relatórios e extrato</Button>}{can('conta.add_'+config.model) && <Button type="primary" aria-label={createLabel} icon={<PlusOutlined />} onClick={() => edit('new')}>{createLabel}</Button>}</Space></div>
    <section className="table-panel print-hidden"><div className="table-toolbar"><Space wrap><Input aria-label="Buscar registro" placeholder="Buscar registro" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} allowClear style={{ width: 240 }} />{resource === 'movimentos' && <Select aria-label="Filtrar movimento" placeholder="Créditos e débitos" value={filter.tipo_movimento} allowClear onChange={v => updateFilter('tipo_movimento', v)} options={[{ value: 'C', label: 'Créditos' }, { value: 'D', label: 'Débitos' }]} style={{ width: 180 }} />}{resource === 'transferencias' && <Select aria-label="Integridade da transferência" placeholder="Todas as transferências" value={filter.integridade} allowClear onChange={v => updateFilter('integridade', v)} options={consistencyOptions} style={{ width: 230 }} />}</Space><Button aria-label="Atualizar registros" icon={<ReloadOutlined />} onClick={() => setReload(v => v + 1)} loading={loading} /></div>
    {error && <Alert type="error" showIcon title={error} />}
    <Table<BankRow> rowKey="id" dataSource={data.results} loading={loading} columns={[...columns, { title: 'Ações', width: 140, render: (_, row) => <Space size={0}><Button type="text" aria-label={'Ver '+config.single} icon={<EyeOutlined />} onClick={() => setDetail(row)} />{can('conta.change_'+config.model) && row.editavel !== false && <Button type="text" aria-label={'Editar '+config.single} icon={<EditOutlined />} onClick={() => edit(row)} />}{can('conta.delete_'+config.model) && row.editavel !== false && <DeleteConfirmation recordName={String(row.descricao ?? row.nome ?? row.nr_documento ?? row.historico ?? `#${row.id}`)} title={resource === 'transferencias' ? 'Excluir transferência e seus dois movimentos?' : 'Excluir '+config.single+'?'} description="Períodos fechados e registros vinculados serão preservados." okText="Excluir" cancelText="Cancelar" onConfirm={() => remove(row)}><Button type="text" danger aria-label={'Excluir '+config.single} icon={<DeleteOutlined />} /></DeleteConfirmation>}</Space> }]} scroll={{ x: 900 }} locale={{ emptyText: <Empty description="Nenhum registro encontrado." /> }} pagination={{ current: page, pageSize: 20, total: data.count, showSizeChanger: false, onChange: setPage }} /></section>
    <Drawer title={(editor === 'new' ? 'Novo cadastro' : 'Editar cadastro')+' · '+config.title} open={!!editor} size={680} destroyOnHidden maskClosable={!saving} onClose={() => { if (!saving) { generation.current++; setEditor(null); } }} footer={<Button type="primary" loading={saving} onClick={() => form.submit()}>Salvar cadastro</Button>}>
      {saveError && <Alert type="error" title={saveError} showIcon style={{ marginBottom: 16 }} />}<Form form={form} layout="vertical" onFinish={save} scrollToFirstError><BankingForm resource={resource} /></Form>
    </Drawer>
    <Drawer className="contract-details" title={'Detalhes · '+config.title} open={!!detail} size={740} destroyOnHidden onClose={() => setDetail(null)}>
      {detail && <>{resource === 'transferencias' && detail.editavel === false && <Alert type="warning" title="Conciliação necessária: os movimentos desta transferência estão ausentes ou inconsistentes." style={{ marginBottom: 20 }} />}<Button className="print-hidden" icon={<PrinterOutlined />} aria-label="Imprimir registro" onClick={() => printSheet('print-bank-document')} style={{ marginBottom: 20 }}>Imprimir registro</Button><article className="contract-printable print-sheet" id="print-bank-document"><PrintHeader title={config.title} reference={`Registro #${detail.id}`}/><Descriptions bordered column={1} items={(resource === 'bancos' ? [['Código', detail.codigo], ['Banco', detail.nome]] : resource === 'contas' ? [['Descrição', detail.descricao], ['Banco', detail.banco_nome], ['Agência', `${detail.agencia}-${detail.dv_agencia}`], ['Conta', `${detail.numeroconta}${detail.dv_conta ? '-'+detail.dv_conta : ''}`], ['Plano de contas', detail.plano_descricao]] : [['Data', dayjs(String(detail.dt_movimento)).format('DD/MM/YYYY')], ...(resource === 'movimentos' ? [['Conta', detail.conta_nome], ['Tipo', detail.tipo_movimento === 'C' ? 'Crédito' : 'Débito'], ['Origem', detail.transferencia ? `Transferência #${detail.transferencia}` : detail.receita ? `Recebimento #${detail.receita}` : detail.despesa ? `Pagamento #${detail.despesa}` : 'Manual']] : [['Origem', detail.origem_nome], ['Destino', detail.destino_nome]]), ['Valor', money(detail.valor)], ['Documento', detail.nr_documento], ['Histórico', detail.historico], ['Último responsável', detail.usuario_nome]]).map(([label, value], i) => ({ key: i, label: String(label), children: text(value) }))} /><PrintFooter/></article></>}
    </Drawer>
    <Modal title="Gerar relatório" open={reportOpen} destroyOnHidden okText="Gerar relatório" cancelText="Voltar" confirmLoading={reportLoading} onCancel={() => { if (!reportLoading) { setReportOpen(false); setParams({}); } }} onOk={() => reportForm.submit()}>
      {reportError && <Alert type="error" title={reportError} showIcon />}<Form form={reportForm} layout="vertical" onFinish={generate} initialValues={{ kind: params.get('relatorio') ?? (resource === 'transferencias' ? 'transferencias' : 'movimentos'), dt_inicial: dayjs().startOf('month').format('YYYY-MM-DD'), dt_final: dayjs().endOf('month').format('YYYY-MM-DD') }}>
      <Form.Item name="kind" label="Tipo de relatório" rules={required}><Select options={resource === 'transferencias' ? [{ value: 'transferencias', label: 'Transferências' }] : [{ value: 'movimentos', label: 'Movimentações' }, { value: 'extrato', label: 'Extrato por conta' }, { value: 'cheques', label: 'Cheques emitidos' }]} /></Form.Item>
      {resource === 'movimentos' ? <Form.Item name="conta" label="Conta do relatório" rules={reportKind === 'extrato' ? required : []}><AccountSelect /></Form.Item> : <><Form.Item name="conta_origem" label="Filtrar conta de origem"><AccountSelect /></Form.Item><Form.Item name="conta_destino" label="Filtrar conta de destino"><AccountSelect /></Form.Item><Form.Item name="integridade" label="Integridade"><Select allowClear options={consistencyOptions} /></Form.Item></>}
      <Row gutter={16}><Col span={12}><DateInput name="dt_inicial" label="Data inicial" /></Col><Col span={12}><DateInput name="dt_final" label="Data final" /></Col></Row></Form>
    </Modal>
    {report && <section className="table-panel report-output print-sheet print-landscape" id="print-bank-report"><PrintHeader title={reportTitle} subtitle={`${printPeriod} · ${report.count} registros`} reference="Relatório bancário" printOnly/><div className="table-toolbar print-hidden"><strong>{reportTitle} · {report.count} registros</strong><Space className="print-hidden"><Button icon={<DownloadOutlined />} disabled={!report.results.length} onClick={csv}>Exportar CSV</Button><Button icon={<PrinterOutlined />} aria-label="Imprimir relatório" onClick={() => printSheet('print-bank-report')}>Imprimir relatório</Button></Space></div>
      <div className="print-summary" style={{ padding: '0 20px 20px' }}><Space wrap>{report.saldo_anterior != null && <span>Saldo anterior: <strong>{money(report.saldo_anterior)}</strong></span>}{report.creditos != null && <span>Créditos: <strong>{money(report.creditos)}</strong></span>}{report.debitos != null && <span>Débitos: <strong>{money(report.debitos)}</strong></span>}{report.saldo_periodo != null && <span>Resultado do período: <strong>{money(report.saldo_periodo)}</strong></span>}{report.saldo_final != null && <span>Saldo final: <strong>{money(report.saldo_final)}</strong></span>}{report.valor_total != null && <span>Total transferido: <strong>{money(report.valor_total)}</strong></span>}</Space></div>
      <Table<BankRow> rowKey="id" dataSource={report.results} columns={columns} pagination={false} scroll={{ x: 800 }} /><PrintFooter/></section>}
  </>;
}
