import { DeleteConfirmation } from '../components/DeleteConfirmation';
import { Table } from '../components/DataTable';
import { PrintHeader, PrintFooter, printSheet } from '../components/PrintLayout';
import { useEffect, useState, type ComponentProps } from 'react';
import { Alert, App, Button, DatePicker, Descriptions, Drawer, Empty, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Tag } from 'antd';
import { DownloadOutlined, EditOutlined, EyeOutlined, PlusOutlined, PrinterOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useSearchParams } from 'react-router-dom';
import { api, ApiError, errorMessage } from '../api';
import { useSession } from '../session';
import { RemoteSelect } from '../components/RemoteSelect';
import type { Page } from '../types';

export type FinancialResource = 'receitas' | 'despesas' | 'fechamentos';
interface FinanceRow { id: number; numero?: string; descricao?: string; parte_nome?: string; dt_vencimento?: string; valor?: string; total_baixado?: string; saldo?: string; situacao_atual?: string; conta_nome?: string; data?: string; receitas?: string; despesas?: string; saldo_anterior?: string; [key: string]: unknown }
interface Baixa { id: number; conta_nome: string; dt_pagamento: string; valor: string; obs: string; numero_cheque?: string }
interface Report extends Page<FinanceRow> { valor_total?: string; total_baixado?: string; saldo_total?: string }
interface Preview { token: string; documento: string; historico: string; dt_pagamento: string; valor: string }
interface Analysis { results: FinanceRow[]; totais: Record<string, string> }
const base = '/financeiro/api/';
const required = [{ required: true, message: 'Preencha este campo.' }];
const money = (value: unknown, precision = 2) => Number(value ?? 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: precision, maximumFractionDigits: precision });
const showDate = (value: string) => value ? dayjs(value).format('DD/MM/YYYY') : '—';
const emptyPage: Report = { count: 0, results: [], next: null, previous: null };
function DateField({ name, label }: { name: string; label: string }) {
  return <Form.Item name={name} label={label} rules={required} getValueProps={v => ({ value: v ? dayjs(v) : null })} normalize={v => v?.format('YYYY-MM-DD') ?? null}><DatePicker format="DD/MM/YYYY" style={{ width: '100%' }} /></Form.Item>;
}
function OptionSelect({ kind, ...props }: Omit<ComponentProps<typeof RemoteSelect>, 'url'> & { kind: string }) {
  return <RemoteSelect {...props} url={base+'opcoes/?tipo='+kind} labelField="descricao" />;
}
function csvDownload(rows: unknown[][], filename: string) {
  const escape = (v: unknown) => { let s = String(v ?? ''); if (/^[=+\-@\t\r]/.test(s)) s = "'"+s; return '"'+s.replace(/"/g, '""')+'"'; };
  const url = URL.createObjectURL(new Blob(['\uFEFF'+rows.map(row => row.map(escape).join(';')).join('\r\n')], { type: 'text/csv;charset=utf-8;' }));
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
}

export function Financial({ resource }: { resource: FinancialResource }) {
  const { empresa, can } = useSession(), { message } = App.useApp();
  const [params] = useSearchParams();
  const receipt = resource === 'receitas', closing = resource === 'fechamentos';
  const title = receipt ? 'Contas a receber' : closing ? 'Fechamentos de caixa' : 'Contas a pagar';
  const model = receipt ? 'docreceita' : closing ? 'fechamentocaixa' : 'docdespesa';
  const paymentModel = receipt ? 'recreceita' : 'pagdespesa';
  const endpoint = base+resource+'/';
  const [form] = Form.useForm(), [paymentForm] = Form.useForm(), [duplicateForm] = Form.useForm(), [analysisForm] = Form.useForm();
  const paymentType = Form.useWatch('forma_pagamento', paymentForm);
  const [data, setData] = useState<Report>(emptyPage), [page, setPage] = useState(1), [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Record<string, string>>(params.get('situacao') ? { situacao: params.get('situacao')! } : {});
  const [loading, setLoading] = useState(false), [error, setError] = useState(''), [reload, setReload] = useState(0);
  const [editor, setEditor] = useState<FinanceRow | 'new' | null>(null), [saving, setSaving] = useState(false), [saveError, setSaveError] = useState('');
  const [detail, setDetail] = useState<FinanceRow | null>(null), [payments, setPayments] = useState<Baixa[]>([]), [detailError, setDetailError] = useState('');
  const [paymentOpen, setPaymentOpen] = useState(false), [paymentKey, setPaymentKey] = useState(''), [paymentError, setPaymentError] = useState('');
  const [duplicate, setDuplicate] = useState<FinanceRow | null>(null), [duplicateError, setDuplicateError] = useState('');
  const [exporting, setExporting] = useState(false), [analysisOpen, setAnalysisOpen] = useState(params.has('analise')), [analysis, setAnalysis] = useState<Analysis | null>(null), [analysisError, setAnalysisError] = useState(''), [analysisPeriod, setAnalysisPeriod] = useState('');
  const [reconcileOpen, setReconcileOpen] = useState(params.has('conciliar'));
  function refresh() { setReload(n => n+1); }
  function filter(name: string, value?: string) { setFilters(old => { const next = { ...old }; if (value) next[name] = value; else delete next[name]; return next; }); setPage(1); }
  useEffect(() => {
    let alive = true; const controller = new AbortController(); setLoading(true); setError('');
    const timer = setTimeout(() => {
      const query = new URLSearchParams({ page: String(page), page_size: '20', search, ...filters });
      api<Report>(endpoint+(closing ? '' : 'relatorio/')+'?'+query, { signal: controller.signal }, empresa)
        .then(value => { if (alive) setData(value); }).catch(e => { if (alive) setError(errorMessage(e)); }).finally(() => { if (alive) setLoading(false); });
    }, search ? 250 : 0);
    return () => { alive = false; controller.abort(); clearTimeout(timer); };
  }, [endpoint, closing, empresa, page, search, filters, reload]);
  useEffect(() => {
    if (editor) { form.resetFields(); form.setFieldsValue(editor === 'new' ? { dt_vencimento: dayjs().format('YYYY-MM-DD'), dt_inicial: dayjs().format('YYYY-MM-DD'), dt_final: dayjs().format('YYYY-MM-DD') } : editor); }
  }, [editor, form]);
  async function edit(row: FinanceRow | 'new') {
    setSaveError('');
    if (row === 'new') { setEditor(row); return; }
    try { setEditor(await api<FinanceRow>(endpoint+row.id+'/', {}, empresa)); } catch (e) { void message.error(errorMessage(e)); }
  }
  async function save(values: Record<string, unknown>) {
    if (!editor) return; setSaving(true); setSaveError('');
    try { await api(endpoint+(editor === 'new' ? '' : editor.id+'/'), { method: editor === 'new' ? 'POST' : 'PATCH', body: JSON.stringify(values) }, empresa); setEditor(null); refresh(); void message.success(closing ? 'Período fechado.' : 'Documento salvo.'); }
    catch (e) { setSaveError(errorMessage(e)); if (e instanceof ApiError && e.status === 400) form.setFields(Object.entries(e.data).filter(([, errors]) => Array.isArray(errors)).map(([name, errors]) => ({ name, errors: errors as string[] }))); }
    finally { setSaving(false); }
  }
  async function showDetail(row: FinanceRow) {
    setDetailError(''); setPayments([]); setDetail(row);
    try {
      const current = await api<FinanceRow>(endpoint+row.id+'/', {}, empresa); setDetail(current);
      if (!closing && can('financeiro.view_'+paymentModel)) {
        let next: string | null = endpoint+row.id+'/baixas/?page_size=200'; const items: Baixa[] = [];
        while (next) { const result: Page<Baixa> = await api(next, {}, empresa); items.push(...result.results); next = result.next ? new URL(result.next, location.origin).pathname+new URL(result.next, location.origin).search : null; }
        setPayments(items);
      }
    } catch (e) { setDetailError(errorMessage(e)); }
  }
  async function remove(row: FinanceRow) {
    try { await api(endpoint+row.id+'/', { method: 'DELETE' }, empresa); setDetail(null); if (page > 1 && data.results.length === 1) setPage(page-1); else refresh(); void message.success('Documento excluído.'); }
    catch (e) { void message.error(errorMessage(e)); }
  }
  async function pay(values: Record<string, unknown>) {
    if (!detail) return; setSaving(true); setPaymentError('');
    try { await api(endpoint+detail.id+'/baixar/', { method: 'POST', body: JSON.stringify({ ...values, idempotencia: paymentKey }) }, empresa); setPaymentOpen(false); refresh(); await showDetail(detail); void message.success('Baixa registrada.'); }
    catch (e) { setPaymentError(errorMessage(e)); } finally { setSaving(false); }
  }
  async function reverse(id: number) {
    if (!detail) return; setSaving(true); setDetailError('');
    try { const result = await api<{detail: string}>(endpoint+detail.id+'/estornar/', { method: 'POST', body: JSON.stringify({ baixa: id }) }, empresa); refresh(); await showDetail(detail); void message.success(result.detail); }
    catch (e) { setDetailError(errorMessage(e)); } finally { setSaving(false); }
  }
  async function reopen(row: FinanceRow) {
    setSaving(true);
    try { await api(endpoint+row.id+'/reabrir/', { method: 'POST' }, empresa); setDetail(null); refresh(); void message.success('Último fechamento reaberto.'); }
    catch (e) { void message.error(errorMessage(e)); } finally { setSaving(false); }
  }
  async function duplicateExpense(values: Record<string, unknown>) {
    if (!duplicate) return; setSaving(true); setDuplicateError('');
    try { await api(endpoint+duplicate.id+'/duplicar/', { method: 'POST', body: JSON.stringify(values) }, empresa); setDuplicate(null); refresh(); void message.success('Despesas criadas.'); }
    catch (e) { setDuplicateError(errorMessage(e)); } finally { setSaving(false); }
  }
  async function exportAll() {
    setExporting(true);
    try {
      let next: string | null = endpoint+(closing ? '' : 'relatorio/')+'?'+new URLSearchParams({ page_size: '200', search, ...filters }); const rows: FinanceRow[] = [];
      while (next) { const value: Report = await api(next, {}, empresa); rows.push(...value.results); next = value.next ? new URL(value.next, location.origin).pathname+new URL(value.next, location.origin).search : null; }
      csvDownload(closing ? [['Data', 'Conta', 'Anterior', 'Receitas', 'Despesas', 'Saldo'], ...rows.map(r => [r.data, r.conta_nome, r.saldo_anterior, r.receitas, r.despesas, r.saldo])] : [['Documento', 'Cliente/Fornecedor', 'Descrição', 'Vencimento', 'Valor', 'Baixado', 'Saldo', 'Situação'], ...rows.map(r => [r.numero, r.parte_nome, r.descricao, r.dt_vencimento, r.valor, r.total_baixado, r.saldo, r.situacao_atual])], resource+'.csv');
    } catch (e) { void message.error(errorMessage(e)); } finally { setExporting(false); }
  }
  async function generateAnalysis(values: Record<string, string>) {
    setSaving(true); setAnalysisError('');
    try { setAnalysis(await api<Analysis>(endpoint+'analise/?'+new URLSearchParams(values), {}, empresa)); setAnalysisPeriod(`Período de ${dayjs(values.dt_inicial).format('DD/MM/YYYY')} a ${dayjs(values.dt_final).format('DD/MM/YYYY')}`); setAnalysisOpen(false); }
    catch (e) { setAnalysisError(errorMessage(e)); } finally { setSaving(false); }
  }
  const columns = closing ? [
    { title: 'Data', dataIndex: 'data', render: showDate }, { title: 'Conta', dataIndex: 'conta_nome' },
    ...['saldo_anterior', 'receitas', 'despesas', 'saldo'].map((name, index) => ({ title: ['Saldo anterior', 'Créditos', 'Débitos', 'Saldo final'][index], dataIndex: name, render: (v: string) => money(v, 4) })),
  ] : [
    { title: 'Documento', dataIndex: 'numero' }, { title: receipt ? 'Cliente' : 'Fornecedor', dataIndex: 'parte_nome' }, { title: 'Vencimento', dataIndex: 'dt_vencimento', render: showDate },
    ...['valor', 'total_baixado', 'saldo'].map((name, index) => ({ title: ['Valor', 'Baixado', 'Em aberto'][index], dataIndex: name, render: (v: string) => money(v) })),
    { title: 'Situação', dataIndex: 'situacao_atual', render: (v: string) => <Tag color={v === 'Vencido' ? 'red' : 'default'}>{v}</Tag> },
  ];
  const creationLabel = closing ? 'Fechar período' : receipt ? 'Nova receita' : 'Nova despesa';
  const canAnalysis = can('financeiro.view_docreceita') && can('financeiro.view_docdespesa');
  const months = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
  return <>
    <div className="page-heading"><div><div className="eyebrow">FINANCEIRO</div><h1>{title}<span className="count-pill">{data.count}</span></h1><p>{closing ? 'Feche períodos e confira os saldos de cada conta.' : 'Acompanhe vencimentos, baixas parciais e o saldo de cada documento.'}</p></div><Space wrap>
      {receipt && can('financeiro.add_recreceita') && <Button onClick={() => setReconcileOpen(true)}>Conciliar extrato</Button>}
      {closing && canAnalysis && <Button onClick={() => setAnalysisOpen(true)}>Análise financeira</Button>}
      {can('financeiro.add_'+model) && <Button type="primary" aria-label={creationLabel} icon={<PlusOutlined />} onClick={() => edit('new')}>{creationLabel}</Button>}
    </Space></div>
    <section className="table-panel print-hidden financial-table"><div className="table-toolbar"><Space wrap>
      {!closing && <Input aria-label="Buscar documento" placeholder="Documento, nome ou descrição" value={search} allowClear onChange={e => { setSearch(e.target.value); setPage(1); }} style={{ width: 250 }} />}
      {!closing && <Select aria-label="Situação financeira" placeholder="Todas as situações" value={filters.situacao} allowClear style={{ width: 190 }} options={[{ value: 'aberto', label: 'Em aberto' }, { value: 'quitado', label: 'Quitados' }, { value: 'vencido', label: 'Vencidos' }]} onChange={v => filter('situacao', v)} />}
      <DatePicker.RangePicker aria-label="Período" format="DD/MM/YYYY" onChange={v => { setFilters(old => { const next = { ...old }; if (v?.[0] && v[1]) { next.dt_inicial = v[0].format('YYYY-MM-DD'); next.dt_final = v[1].format('YYYY-MM-DD'); } else { delete next.dt_inicial; delete next.dt_final; } return next; }); setPage(1); }} />
      {closing && <div style={{ width: 220 }}><OptionSelect kind="contas" placeholder="Filtrar conta" value={filters.conta ? Number(filters.conta) : undefined} onChange={v => filter('conta', v ? String(v) : undefined)} /></div>}
    </Space><Space><Button aria-label="Atualizar financeiro" icon={<ReloadOutlined />} onClick={refresh} loading={loading} /><Button aria-label="Exportar CSV" icon={<DownloadOutlined />} onClick={exportAll} loading={exporting}>Exportar CSV</Button></Space></div>
    {!closing && <div className="financial-totals"><span>Total: <strong>{money(data.valor_total)}</strong></span><span>Baixado: <strong>{money(data.total_baixado)}</strong></span><span>Em aberto: <strong>{money(data.saldo_total)}</strong></span></div>}
    {error && <Alert type="error" showIcon title={error} />}
    <Table<FinanceRow> rowKey="id" dataSource={data.results} loading={loading} columns={[...columns, { title: 'Ações', render: (_, row) => <Space size={0}><Button type="text" aria-label="Ver documento" icon={<EyeOutlined />} onClick={() => showDetail(row)} />{!closing && can('financeiro.change_'+model) && Number(row.total_baixado) === 0 && <Button type="text" aria-label="Editar documento" icon={<EditOutlined />} onClick={() => edit(row)} />}</Space> }]} scroll={{ x: 1000 }} locale={{ emptyText: <Empty description="Nenhum registro encontrado." /> }} pagination={{ current: page, pageSize: 20, total: data.count, showSizeChanger: false, onChange: setPage }} />
    </section>
    <Drawer title={editor === 'new' ? creationLabel : 'Editar documento'} open={!!editor} size={650} destroyOnHidden onClose={() => { if (!saving) setEditor(null); }} footer={<Button type="primary" loading={saving} onClick={() => form.submit()}>{closing ? 'Confirmar fechamento' : 'Salvar documento'}</Button>}>
      {saveError && <Alert type="error" title={saveError} showIcon />}<Form form={form} layout="vertical" onFinish={save}>
        {closing ? <><Alert type="info" title="Após o fechamento, as movimentações do período ficam bloqueadas para edição." style={{ marginBottom: 20 }} /><Form.Item name="conta" label="Conta bancária" rules={required}><OptionSelect kind="contas" /></Form.Item><DateField name="dt_inicial" label="Data inicial" /><DateField name="dt_final" label="Data final" /></> : <>
          <Form.Item name={receipt ? 'cliente' : 'fornecedor'} label={receipt ? 'Cliente' : 'Fornecedor'} rules={required}><OptionSelect kind={receipt ? 'clientes' : 'fornecedores'} disabled={receipt && editor !== 'new'} /></Form.Item>
          {receipt && <Form.Item name="nota" label="Nota fiscal" rules={required}><OptionSelect kind="notas" disabled={editor !== 'new'} /></Form.Item>}
          <Form.Item name="numero" label="Número do documento" rules={required}><Input maxLength={30} /></Form.Item><Form.Item name="descricao" label="Descrição" rules={required}><Input.TextArea rows={3} maxLength={receipt ? undefined : 500} /></Form.Item>
          <DateField name="dt_vencimento" label="Vencimento" /><Form.Item name="valor" label="Valor do documento" rules={required}><InputNumber<string> stringMode min="0.01" max="99999999.99" precision={2} decimalSeparator="," prefix="R$" style={{ width: '100%' }} /></Form.Item>
          {!receipt && <><Form.Item name="tipo_despesa" label="Tipo de despesa"><OptionSelect kind="tipos" /></Form.Item><Form.Item name="centro_custo" label="Centro de custo"><OptionSelect kind="centros" /></Form.Item></>}
        </>}
      </Form>
    </Drawer>
    <Drawer title={closing ? 'Fechamento' : 'Documento e baixas'} className="contract-details" open={!!detail} size={850} destroyOnHidden onClose={() => { if (!saving) setDetail(null); }}>
      {detail && <><Space wrap className="print-hidden" style={{ marginBottom: 20 }}><Button icon={<PrinterOutlined />} aria-label="Imprimir documento" onClick={() => printSheet('print-financial-document')}>Imprimir documento</Button>
        {!closing && can('financeiro.add_'+paymentModel) && Number(detail.saldo) > 0 && <Button type="primary" onClick={() => { paymentForm.resetFields(); paymentForm.setFieldsValue({ dt_pagamento: dayjs().format('YYYY-MM-DD'), valor: detail.saldo, forma_pagamento: 'T' }); setPaymentKey(crypto.randomUUID()); setPaymentError(''); setPaymentOpen(true); }}>{receipt ? 'Registrar recebimento' : 'Registrar pagamento'}</Button>}
        {!closing && can('financeiro.delete_'+model) && Number(detail.total_baixado) === 0 && <DeleteConfirmation recordName={String(detail.numero ?? detail.descricao ?? `#${detail.id}`)} title="Excluir documento sem baixas?" okText="Excluir" cancelText="Cancelar" onConfirm={() => remove(detail)}><Button danger>Excluir documento</Button></DeleteConfirmation>}
        {!receipt && !closing && can('financeiro.add_docdespesa') && <Button onClick={() => { duplicateForm.resetFields(); setDuplicateError(''); setDuplicate(detail); }}>Duplicar mensalmente</Button>}
        {closing && can('financeiro.delete_fechamentocaixa') && <Popconfirm title="Reabrir este fechamento?" description="Somente o último fechamento da conta pode ser reaberto." okText="Reabrir" cancelText="Voltar" onConfirm={() => reopen(detail)}><Button danger loading={saving}>Reabrir caixa</Button></Popconfirm>}
      </Space>{detailError && <Alert type="error" title={detailError} showIcon />}
      <article className="contract-printable print-sheet" id="print-financial-document"><PrintHeader title={title} reference={closing ? 'Fechamento de caixa' : `Documento ${detail.numero ?? detail.id}`}/><Descriptions bordered column={1} items={(closing ? [['Data', showDate(String(detail.data))], ['Conta', detail.conta_nome], ['Saldo anterior', money(detail.saldo_anterior, 4)], ['Créditos', money(detail.receitas, 4)], ['Débitos', money(detail.despesas, 4)], ['Saldo final', money(detail.saldo, 4)]] : [['Documento', detail.numero], [receipt ? 'Cliente' : 'Fornecedor', detail.parte_nome], ['Descrição', detail.descricao], ['Vencimento', showDate(String(detail.dt_vencimento))], ['Valor', money(detail.valor)], ['Baixado', money(detail.total_baixado)], ['Em aberto', money(detail.saldo)], ['Situação', detail.situacao_atual], ['Responsável', detail.usuario_nome]]).map(([label, value], i) => ({ key: i, label: String(label), children: String(value ?? '—') }))} />
      {!closing && can('financeiro.view_'+paymentModel) && <><h3>{receipt ? 'Recebimentos' : 'Pagamentos'}</h3><Table<Baixa> rowKey="id" dataSource={payments} pagination={false} scroll={{ x: 650 }} columns={[{ title: 'Data', dataIndex: 'dt_pagamento', render: showDate }, { title: 'Conta', dataIndex: 'conta_nome' }, { title: 'Valor', dataIndex: 'valor', render: (v: string) => money(v) }, { title: 'Observação', dataIndex: 'obs' }, { title: 'Cheque', dataIndex: 'numero_cheque' }, { title: 'Ação', className: 'print-hidden', render: (_, row) => can('financeiro.delete_'+paymentModel) && <Popconfirm title="Estornar somente esta baixa?" description="O movimento vinculado será removido e o saldo será recalculado." okText="Estornar" cancelText="Voltar" onConfirm={() => reverse(row.id)}><Button danger loading={saving}>Estornar</Button></Popconfirm> }]} /></>}
      <PrintFooter/></article></>}
    </Drawer>
    <Modal title={receipt ? 'Registrar recebimento' : 'Registrar pagamento'} open={paymentOpen} okText="Confirmar baixa" cancelText="Voltar" confirmLoading={saving} onCancel={() => { if (!saving) setPaymentOpen(false); }} onOk={() => paymentForm.submit()}>
      {paymentError && <Alert type="error" showIcon title={paymentError} />}<Form form={paymentForm} layout="vertical" onFinish={pay}>
        <Form.Item name="conta" label="Conta da baixa" rules={required}><OptionSelect kind="contas" /></Form.Item><DateField name="dt_pagamento" label="Data da baixa" /><Form.Item name="valor" label="Valor da baixa" rules={required}><InputNumber<string> stringMode min="0.01" max={detail?.saldo ?? '99999999.99'} precision={2} decimalSeparator="," prefix="R$" style={{ width: '100%' }} /></Form.Item>
        {!receipt && <><Form.Item name="forma_pagamento" label="Forma de pagamento" rules={required}><Select options={[{ value: 'D', label: 'Dinheiro' }, { value: 'C', label: 'Cheque' }, { value: 'T', label: 'Transação bancária' }, { value: 'E', label: 'Cartão Visa' }]} /></Form.Item>{paymentType === 'C' && <Form.Item name="numero_cheque" label="Número do cheque" rules={required}><Input maxLength={10} /></Form.Item>}</>}
        <Form.Item name="obs" label="Observação"><Input.TextArea rows={2} maxLength={200} /></Form.Item>
      </Form>
    </Modal>
    <Modal title="Duplicar despesa mensalmente" open={!!duplicate} okText="Criar despesas" cancelText="Voltar" confirmLoading={saving} onCancel={() => { if (!saving) setDuplicate(null); }} onOk={() => duplicateForm.submit()}>
      {duplicateError && <Alert type="error" title={duplicateError} />}<p>A primeira cópia vence na data informada. As demais vencem nos meses seguintes, ajustando para o último dia quando necessário.</p><Form form={duplicateForm} layout="vertical" onFinish={duplicateExpense}><Form.Item name="quantidade" label="Quantidade de cópias" rules={required}><InputNumber min={1} max={60} precision={0} /></Form.Item><DateField name="primeiro_vencimento" label="Primeiro vencimento" /></Form>
    </Modal>
    {receipt && can('financeiro.add_recreceita') && <Reconciliation open={reconcileOpen} onClose={() => setReconcileOpen(false)} onDone={refresh} />}
    <Modal title="Análise financeira" open={closing && analysisOpen && canAnalysis} okText="Gerar análise" cancelText="Voltar" confirmLoading={saving} onCancel={() => { if (!saving) setAnalysisOpen(false); }} onOk={() => analysisForm.submit()}>
      {analysisError && <Alert type="error" title={analysisError} />}<Form form={analysisForm} layout="vertical" onFinish={generateAnalysis} initialValues={{ dt_inicial: dayjs().startOf('year').format('YYYY-MM-DD'), dt_final: dayjs().endOf('year').format('YYYY-MM-DD') }}><DateField name="dt_inicial" label="Data inicial" /><DateField name="dt_final" label="Data final" /></Form>
    </Modal>
    {analysis && <section className="table-panel report-output print-sheet print-landscape" id="print-financial-analysis"><div className="table-toolbar print-hidden"><strong>Análise · previsto e realizado</strong><Space className="print-hidden"><Button onClick={() => csvDownload([['Tipo', 'Ano', 'Centro', 'Categoria', ...months.flatMap(m => [m+' previsto', m+' realizado'])], ...analysis.results.map(r => [r.tipo_movimento, r.exercicio, r.centrocusto, r.tipodespesa, ...months.flatMap(m => [r[m+'p'], r[m+'r']])])], 'analise-financeira.csv')}>Exportar análise</Button><Button aria-label="Imprimir análise" onClick={() => printSheet('print-financial-analysis')}>Imprimir análise</Button></Space></div><Table<FinanceRow> className="analysis-screen" rowKey="id" dataSource={analysis.results} pagination={false} scroll={{ x: 2600 }} columns={[{ title: 'Tipo', dataIndex: 'tipo_movimento' }, { title: 'Ano', dataIndex: 'exercicio' }, { title: 'Centro', dataIndex: 'centrocusto' }, { title: 'Categoria', dataIndex: 'tipodespesa' }, ...months.map(m => ({ title: m.toUpperCase(), children: [{ title: 'Previsto', dataIndex: m+'p', render: (v: string) => money(v) }, { title: 'Realizado', dataIndex: m+'r', render: (v: string) => money(v) }] }))]} /><div className="financial-totals analysis-screen">{months.map(m => <span key={m}>{m.toUpperCase()} líquido: <strong>{money(analysis.totais[m+'v'])}</strong></span>)}</div><div className="layout-print-only">{[0, 1, 2, 3].map(quarter => <section className="print-quarter" key={quarter}>
      <PrintHeader title="Análise financeira" subtitle={analysisPeriod} reference={`${quarter + 1}º trimestre · previsto e realizado`}/>
      <Table<FinanceRow> tableActions={false} rowKey="id" dataSource={analysis.results} pagination={false} columns={[{title:'Tipo',dataIndex:'tipo_movimento'},{title:'Ano',dataIndex:'exercicio'},{title:'Centro',dataIndex:'centrocusto'},{title:'Categoria',dataIndex:'tipodespesa'},...months.slice(quarter*3,quarter*3+3).map(month=>({title:month.toUpperCase(),children:[{title:'Previsto',dataIndex:month+'p',render:(value:string)=>money(value)},{title:'Realizado',dataIndex:month+'r',render:(value:string)=>money(value)}]}))]}/>
      <div className="financial-totals">{months.slice(quarter*3,quarter*3+3).map(month=><span key={month}>{month.toUpperCase()} líquido: <strong>{money(analysis.totais[month+'v'])}</strong></span>)}</div><PrintFooter/>
    </section>)}</div></section>}
  </>;
}

function Reconciliation({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { empresa } = useSession(), { message } = App.useApp();
  const [rows, setRows] = useState<Preview[]>([]), [links, setLinks] = useState<Record<string, number>>({});
  const [account, setAccount] = useState<number>(), [busy, setBusy] = useState(false), [error, setError] = useState('');
  useEffect(() => { if (!open) { setRows([]); setLinks({}); setError(''); setAccount(undefined); } }, [open]);
  async function upload(file?: File) {
    if (!file) return; setBusy(true); setError(''); setRows([]); setLinks({});
    const formData = new FormData(); formData.append('extrato', file);
    try { const result = await api<{results: Preview[]}>(base+'receitas/previsualizar/', { method: 'POST', body: formData }, empresa); setRows(result.results); }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  async function confirm() {
    setBusy(true); setError('');
    try { await api(base+'receitas/conciliar/', { method: 'POST', body: JSON.stringify({ conta: account, itens: rows.filter(r => links[r.token]).map(r => ({ token: r.token, receita: links[r.token] })) }) }, empresa); onDone(); onClose(); void message.success('Créditos selecionados conciliados.'); }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  return <Drawer title="Conciliar extrato" open={open} size={1100} destroyOnHidden onClose={() => { if (!busy) onClose(); }} footer={<Popconfirm title="Registrar os créditos vinculados?" description="Confira a conta e o documento de cada linha. As linhas sem vínculo serão ignoradas." okText="Confirmar" cancelText="Voltar" onConfirm={confirm}><Button type="primary" loading={busy} disabled={!account || !Object.keys(links).length}>Confirmar conciliação</Button></Popconfirm>}>
    <Alert type="info" showIcon title="Importe e confira antes de gravar" description="CSV com cabeçalho data;valor;documento;historico, datas DD/MM/AAAA e valores 1.234,56. Também aceita TXT do BB no formato legado. Até 2 MB e 200 créditos; a prévia expira em 30 minutos." style={{ marginBottom: 20 }} />
    {error && <Alert type="error" showIcon title={error} />}<Space vertical style={{ width: '100%', marginBottom: 20 }}><label>Arquivo do extrato <input aria-label="Arquivo do extrato" type="file" accept=".csv,.txt" disabled={busy} onChange={e => { void upload(e.target.files?.[0]); e.target.value = ''; }} /></label><OptionSelect kind="contas" value={account} onChange={setAccount} placeholder="Conta dos créditos" disabled={busy} /></Space>
    <Table<Preview> rowKey="token" dataSource={rows} pagination={{ pageSize: 10 }} loading={busy} scroll={{ x: 800 }} columns={[{ title: 'Data', dataIndex: 'dt_pagamento', render: showDate }, { title: 'Documento do banco', dataIndex: 'documento' }, { title: 'Histórico', dataIndex: 'historico' }, { title: 'Crédito', dataIndex: 'valor', render: (v: string) => money(v) }, { title: 'Vincular receita', width: 330, render: (_, row) => <OptionSelect kind="receitas" value={links[row.token]} disabled={busy} onChange={v => setLinks(old => { const next = { ...old }; if (v) next[row.token] = v; else delete next[row.token]; return next; })} /> }]} />
  </Drawer>;
}
