import { DeleteConfirmation } from '../components/DeleteConfirmation';
import { Table } from '../components/DataTable';
import { PrintHeader, PrintFooter, printSheet } from '../components/PrintLayout';
import { Alert, App, Button, Descriptions, Drawer, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Switch, Tag } from 'antd';
import { DeleteOutlined, EditOutlined, EyeOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import dayjs from 'dayjs';
import { api, ApiError, errorMessage } from '../api';
import { useSession } from '../session';
import type { Page } from '../types';
import type { Note, Operation, FiscalConfig } from '../noteTypes';
import { noteEndpoint as endpoint, noteStates, stateLabel } from '../noteTypes';
import { money } from '../contractTypes';
import { NoteForm } from '../components/NoteForm';
import { RemoteSelect } from '../components/RemoteSelect';
export function Notes() {
  const { empresa, can } = useSession();
  const { message } = App.useApp();
  const [params, setParams] = useSearchParams();
  const [form] = Form.useForm(), [generationForm] = Form.useForm(), [cancelForm] = Form.useForm();
  const [rows, setRows] = useState<Page<Note>>({ count: 0, results: [], next: null, previous: null });
  const [config, setConfig] = useState<FiscalConfig>();
  const [search, setSearch] = useState(''), [state, setState] = useState<string>(), [page, setPage] = useState(1);
  const [reload, setReload] = useState(0), [loading, setLoading] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState(''), [saveError, setSaveError] = useState('');
  const [editor, setEditor] = useState<Note | 'new' | null>(null), [detail, setDetail] = useState<Note | null>(null);
  const [generating, setGenerating] = useState(false), [cancelling, setCancelling] = useState(false);
  const [history, setHistory] = useState<Page<Operation>>({ count: 0, results: [], next: null, previous: null }), [historyPage, setHistoryPage] = useState(1);
  const [operation, setOperation] = useState<Operation>(), [publicLink, setPublicLink] = useState('');
  const required = [{ required: true, message: 'Preencha este campo.' }];
  useEffect(() => {
    let alive = true;
    api<FiscalConfig>(endpoint + 'configuracao/', {}, empresa).then(v => { if (alive) setConfig(v); }).catch(e => { if (alive) setError(errorMessage(e)); });
    return () => { alive = false; };
  }, [empresa]);
  useEffect(() => {
    const controller = new AbortController(); let alive = true;
    setLoading(true); setError('');
    const timer = setTimeout(() => {
      const query = new URLSearchParams({ search, page: String(page), page_size: '20' });
      if (state) query.set('estado', state);
      api<Page<Note>>(endpoint + '?' + query, { signal: controller.signal }, empresa).then(v => { if (alive) setRows(v); }).catch(e => { if (alive) setError(errorMessage(e)); }).finally(() => { if (alive) setLoading(false); });
    }, search ? 250 : 0);
    return () => { alive = false; clearTimeout(timer); controller.abort(); };
  }, [empresa, page, search, state, reload]);
  const detailId = detail?.id;
  useEffect(() => {
    if (!detailId) return;
    let alive = true;
    api<Page<Operation>>(endpoint + detailId + '/historico/?page=' + historyPage, {}, empresa).then(v => { if (alive) setHistory(v); }).catch(e => { if (alive) setSaveError(errorMessage(e)); });
    return () => { alive = false; };
  }, [detailId, empresa, reload, historyPage]);
  useEffect(() => {
    if (editor) { form.resetFields(); form.setFieldsValue(editor === 'new' ? { competencia: dayjs().month() + 1, exercicio: dayjs().year(), dt_data_emissao: dayjs().toISOString(), valor_bruto: '0.00', imposto: '0.00', aliq_imposto: '0.00', valor_liquido: '0.00', coigo_servico: '104', codigo_cnae: '6202300', codigo_tributacao_municipio: '620230000' } : editor); }
  }, [editor, form]);
  useEffect(() => {
    const id = params.get('nota'); if (!id) return; let alive = true;
    api<Note>(endpoint + encodeURIComponent(id) + '/', {}, empresa).then(v => { if (alive) setDetail(v); }).catch(e => { if (alive) void message.error(errorMessage(e)); });
    return () => { alive = false; };
  }, [params, empresa, message]);
  function editable(row: Note) { return row.estado_fiscal === 'rascunho' && !row.tem_financeiro && !row.tem_operacoes; }
  async function refreshDetail(id: number) { setDetail(await api<Note>(endpoint + id + '/', {}, empresa)); setReload(v => v + 1); }
  async function open(row: Note, edit = false) {
    try {
      const value = await api<Note>(endpoint + row.id + '/', {}, empresa);
      setSaveError(''); setOperation(undefined); setPublicLink(''); setHistoryPage(1);
      if (edit) setEditor(value); else setDetail(value);
    } catch (e) { void message.error(errorMessage(e)); }
  }
  async function save(values: Record<string, unknown>) {
    if (!editor) return; setBusy(true); setSaveError('');
    try { await api(endpoint + (editor === 'new' ? '' : editor.id + '/'), { method: editor === 'new' ? 'POST' : 'PATCH', body: JSON.stringify(values) }, empresa); setEditor(null); setReload(v => v + 1); void message.success('Rascunho salvo.'); }
    catch (e) { setSaveError(errorMessage(e)); if (e instanceof ApiError && e.status === 400 && e.data && typeof e.data === 'object') form.setFields(Object.entries(e.data).filter(([, v]) => Array.isArray(v)).map(([name, errors]) => ({ name, errors: errors as string[] }))); }
    finally { setBusy(false); }
  }
  async function remove(row: Note) {
    try { await api(endpoint + row.id + '/', { method: 'DELETE' }, empresa); if (rows.results.length === 1 && page > 1) setPage(page - 1); else setReload(v => v + 1); void message.success('Rascunho excluído.'); } catch (e) { void message.error(errorMessage(e)); }
  }
  async function generate(values: { contratos: { id: number }[]; competencia: number; exercicio: number; decimo_terceiro: boolean }) {
    setBusy(true); setSaveError('');
    try {
      const data = await api<{ results: (Note & { criada: boolean })[] }>(endpoint + 'gerar/', { method: 'POST', body: JSON.stringify({ ...values, contratos: values.contratos.map(c => c.id) }) }, empresa);
      setGenerating(false); setReload(v => v + 1); void message.success(`${data.results.filter(n => n.criada).length} rascunho(s) criado(s); ${data.results.filter(n => !n.criada).length} já existente(s).`);
    } catch (e) { setSaveError(errorMessage(e)); } finally { setBusy(false); }
  }
  async function execute(action: string, justificativa = '') {
    if (!detail) return; const id = detail.id; setBusy(true); setSaveError(''); setOperation(undefined);
    try {
      const data = await api<{ operacao?: Operation; criada?: boolean }>(endpoint + id + '/' + action + '/', { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify({ confirmar: true, justificativa }) }, empresa);
      if (data.operacao) setOperation(data.operacao); else void message.success(data.criada ? 'Receita criada.' : 'Receita existente preservada.');
      setCancelling(false);
    } catch (e) {
      if (e instanceof ApiError && e.data && typeof e.data === 'object' && 'operacao' in e.data) setOperation((e.data as { operacao: Operation }).operacao);
      else setSaveError(errorMessage(e));
    } finally { try { await refreshDetail(id); } catch (e) { setSaveError(errorMessage(e)); } setBusy(false); }
  }
  async function share() {
    if (!detail) return;
    try { const result = await api<{ url: string }>(endpoint + detail.id + '/link_publico/', {}, empresa); setPublicLink(result.url); }
    catch (e) { setSaveError(errorMessage(e)); }
  }
  function action(label: string, name: string, disabled = false) {
    return <Popconfirm key={name} title={`${label}?`} description="A operação será registrada no histórico." okText="Confirmar" cancelText="Voltar" onConfirm={() => execute(name)} disabled={busy || disabled}><Button disabled={busy || disabled}>{label}</Button></Popconfirm>;
  }
  return <>
    <div className="page-heading"><div><div className="eyebrow">GESTÃO / NOTAS FISCAIS</div><h1>Notas fiscais<span className="count-pill">{rows.count}</span></h1><p>Gere rascunhos, acompanhe o processamento e consulte o histórico fiscal.</p></div><Space wrap><Link to="/relatorios?tipo=NF_ALL"><Button>Relatório de notas</Button></Link>{can('notas.add_nota') && <><Button onClick={() => { setSaveError(''); generationForm.resetFields(); setGenerating(true); }}>Gerar por contratos</Button><Button aria-label="Novo rascunho" type="primary" icon={<PlusOutlined />} onClick={() => { setSaveError(''); setEditor('new'); }}>Novo rascunho</Button></>}</Space></div>
    {config && <Alert style={{ marginBottom: 20 }} showIcon type={config.disponivel ? 'info' : 'warning'} title={`Ambiente fiscal: ${config.homologacao === null ? 'não configurado' : config.homologacao ? 'homologação' : 'produção'}`} description={config.pendencias.join(' ') || 'Emissão e cancelamento exigem confirmação explícita.'} />}
    <section className="table-panel"><div className="table-toolbar"><Space wrap><Input aria-label="Buscar nota" placeholder="Número, cliente ou contrato" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} allowClear style={{ width: 250 }} /><Select aria-label="Estado fiscal" placeholder="Todos os estados" value={state} allowClear onChange={v => { setState(v); setPage(1); }} options={noteStates} style={{ width: 190 }} /></Space><Button aria-label="Atualizar notas" icon={<ReloadOutlined />} loading={loading} onClick={() => setReload(v => v + 1)} /></div>
    {error && <Alert type="error" showIcon title={error} />}
    <Table<Note> rowKey="id" loading={loading} dataSource={rows.results} scroll={{ x: 1050 }} columns={[
      { title: 'Nota', dataIndex: 'numero', render: (v, row) => <button className="record-title" onClick={() => open(row)}>{v || `Rascunho #${row.id}`}</button> },
      { title: 'Cliente', dataIndex: 'cliente_nome' }, { title: 'Competência', render: (_, row) => `${String(row.competencia).padStart(2, '0')}/${row.exercicio}` },
      { title: 'Valor líquido', dataIndex: 'valor_liquido', render: money }, { title: 'Estado', dataIndex: 'estado_fiscal', render: v => <Tag color={['incerta', 'cancelada'].includes(v) ? 'red' : 'default'}>{stateLabel(v)}</Tag> },
      { title: 'E-mail', dataIndex: 'ja_enviou', render: v => v ? 'Enviado' : 'Não enviado' },
      { title: 'Ações', render: (_, row) => <Space size={0}><Button type="text" aria-label="Ver nota" icon={<EyeOutlined />} onClick={() => open(row)} />{can('notas.change_nota') && editable(row) && <Button type="text" aria-label="Editar rascunho" icon={<EditOutlined />} onClick={() => open(row, true)} />}{can('notas.delete_nota') && editable(row) && <DeleteConfirmation recordName={String(row.numero ?? `Rascunho #${row.id}`)} title="Excluir rascunho?" okText="Excluir" cancelText="Cancelar" onConfirm={() => remove(row)}><Button type="text" danger aria-label="Excluir rascunho" icon={<DeleteOutlined />} /></DeleteConfirmation>}</Space> },
    ]} pagination={{ current: page, pageSize: 20, total: rows.count, showSizeChanger: false, onChange: setPage }} /></section>
    <Drawer title={editor === 'new' ? 'Novo rascunho' : 'Editar rascunho'} open={!!editor} size={720} destroyOnHidden maskClosable={!busy} onClose={() => { if (!busy) setEditor(null); }} footer={<Button type="primary" aria-label="Salvar rascunho" loading={busy} onClick={() => form.submit()}>Salvar rascunho</Button>}>
      {saveError && <Alert type="error" title={saveError} showIcon />}<Form form={form} layout="vertical" onFinish={save} scrollToFirstError><NoteForm form={form} /></Form>
    </Drawer>
    <Modal title="Gerar rascunhos por contratos" open={generating} destroyOnHidden confirmLoading={busy} okText="Gerar rascunhos" cancelText="Voltar" onCancel={() => { if (!busy) setGenerating(false); }} onOk={() => generationForm.submit()}>
      <p>Esta etapa cria rascunhos. Repita a mesma seleção para reutilizar notas da competência sem duplicar valores.</p>{saveError && <Alert type="error" title={saveError} showIcon />}
      <Form form={generationForm} layout="vertical" initialValues={{ contratos: [{}], competencia: dayjs().month() + 1, exercicio: dayjs().year(), decimo_terceiro: false }} onFinish={generate}>
        <Form.List name="contratos">{(fields, { add, remove }) => <>{fields.map(field => <Space key={field.key} align="start"><Form.Item name={[field.name, 'id']} label={`Contrato ${field.name + 1}`} rules={required} style={{ width: 330, maxWidth: '70vw' }}><RemoteSelect url={endpoint + 'opcoes/'} labelField="descricao" /></Form.Item>{fields.length > 1 && <Button aria-label={`Remover contrato ${field.name + 1}`} onClick={() => remove(field.name)} icon={<DeleteOutlined />} style={{ marginTop: 30 }} />}</Space>)}<Button onClick={() => add({})} disabled={fields.length >= 100}>Adicionar contrato</Button></>}</Form.List>
        <Space wrap><Form.Item name="competencia" label="Mês da competência" rules={required}><InputNumber min={1} max={12} precision={0} /></Form.Item><Form.Item name="exercicio" label="Exercício" rules={required}><InputNumber min={1} max={9999} precision={0} /></Form.Item></Space><Form.Item name="decimo_terceiro" label="Incluir décimo terceiro (dobrar o valor bruto)" valuePropName="checked"><Switch /></Form.Item>
      </Form>
    </Modal>
    <Drawer className="contract-details" title="Detalhes da nota" open={!!detail} size={1000} destroyOnHidden maskClosable={!busy} onClose={() => { if (!busy) { setDetail(null); setParams({}); } }}>
      {detail && <>
        <div className="print-hidden"><Space wrap style={{ marginBottom: 20 }}>
          {can('notas.change_nota') && <>
            {action('Emitir NFS-e', 'emitir', !config?.disponivel || detail.estado_fiscal !== 'rascunho' || !!detail.numero)}
            {action('Consultar nota', 'consultar', !config?.disponivel || (!detail.numero && !detail.protocolo_envio && !detail.numero_rps))}
            <Button danger disabled={busy || !config?.disponivel || detail.estado_fiscal !== 'autorizada' || detail.tem_financeiro} onClick={() => { cancelForm.resetFields(); setCancelling(true); }}>Cancelar NFS-e</Button>
            {action('Enviar por e-mail', 'email', !config?.email_disponivel || detail.estado_fiscal !== 'autorizada')}
            {action('Enviar relação do cliente', 'email_cliente', !config?.email_disponivel || detail.estado_fiscal !== 'autorizada')}
          </>}
          {can('notas.view_nota') && action('Consultar lote', 'consultar_lote', !config?.disponivel || !detail.protocolo_envio)}
          {can('financeiro.add_docreceita') && action('Gerar financeiro', 'financeiro', detail.estado_fiscal !== 'autorizada')}
          <Button disabled={!detail.protocolo_recebimento} onClick={share}>Obter link de consulta</Button><Button aria-label="Imprimir nota" onClick={() => printSheet('print-note')}>Imprimir nota</Button>
        </Space>
        {saveError && <Alert style={{ marginBottom: 16 }} type="error" showIcon title={saveError} />}
        {operation && <Alert style={{ marginBottom: 16 }} showIcon type={operation.estado === 'concluida' ? 'success' : 'warning'} title={`Operação ${operation.acao}: ${operation.estado}`} description={<>{operation.resultado.detail}<ul>{operation.resultado.mensagens?.map((v, i) => <li key={i}>{v.codigo}: {v.mensagem} {v.correcao}</li>)}</ul></>} />}
        {publicLink && <Alert style={{ marginBottom: 16 }} type="info" title="Link temporário de consulta" description={<a href={publicLink} target="_blank" rel="noreferrer">Abrir nota em nova aba</a>} />}
        </div>
        <article className="contract-printable print-sheet" id="print-note"><PrintHeader title={`Nota fiscal de serviços ${detail.numero || `· Rascunho #${detail.id}`}`} reference="Consulta fiscal"/>{detail.estado_fiscal === 'cancelada' && <p className="print-cancelled">NOTA CANCELADA</p>}<p className="print-fiscal-notice">{!detail.protocolo_recebimento ? 'RASCUNHO — SEM VALIDADE FISCAL' : 'Representação para consulta. Verifique a autenticidade junto ao município emissor.'}</p><Tag>{stateLabel(detail.estado_fiscal)}</Tag><Descriptions column={{ xs: 1, sm: 2 }} bordered size="small" style={{ margin: '20px 0' }} items={[
          { key: 'cliente', label: 'Cliente', children: detail.cliente_nome }, { key: 'cnpj', label: 'CNPJ', children: detail.cliente_cnpj },
          { key: 'contrato', label: 'Contrato', children: detail.contrato_numero }, { key: 'mes', label: 'Competência', children: `${detail.competencia}/${detail.exercicio}` },
          { key: 'bruto', label: 'Valor bruto', children: money(detail.valor_bruto) }, { key: 'liquido', label: 'Valor líquido', children: money(detail.valor_liquido) },
          { key: 'imposto', label: 'ISS', children: money(detail.imposto) }, { key: 'aliquota', label: 'Alíquota', children: `${detail.aliq_imposto}%` },
          { key: 'protocolo', label: 'Protocolo de envio', children: detail.protocolo_envio || '—' }, { key: 'autorizacao', label: 'Código de verificação', children: detail.protocolo_recebimento || '—' },
          { key: 'rps', label: 'RPS / Lote', children: `${detail.numero_rps ?? '—'} / ${detail.numero_lote ?? '—'}` }, { key: 'financeiro', label: 'Financeiro vinculado', children: detail.tem_financeiro ? 'Sim' : 'Não' },
        ]} /><h3>Discriminação dos serviços</h3><p style={{ whiteSpace: 'pre-wrap' }}>{detail.texto_nota}</p><PrintFooter/></article>
        <section className="print-hidden"><h3>Histórico de operações</h3><p>Resultados incertos exigem conciliação antes de novas tentativas. A justificativa de cancelamento é registrada para auditoria interna.</p><Table<Operation> rowKey="id" size="small" dataSource={history.results} scroll={{ x: 700 }} columns={[
          { title: 'Data', dataIndex: 'criada_em', render: v => dayjs(v).format('DD/MM/YYYY HH:mm') }, { title: 'Usuário', dataIndex: 'usuario_nome' }, { title: 'Ação', dataIndex: 'acao' }, { title: 'Estado', dataIndex: 'estado' },
          { title: 'Resultado', render: (_, row) => row.resultado.detail || row.resultado.mensagens?.map(m => `${m.codigo}: ${m.mensagem}`).join('; ') || 'Registrado' },
        ]} expandable={{ expandedRowRender: row => <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(row.resultado, null, 2)}</pre> }} pagination={{ current: historyPage, pageSize: 50, total: history.count, showSizeChanger: false, onChange: setHistoryPage }} /></section>
      </>}
    </Drawer>
    <Modal title="Solicitar cancelamento fiscal" open={cancelling} destroyOnHidden okText="Confirmar cancelamento" cancelText="Voltar" confirmLoading={busy} onCancel={() => { if (!busy) setCancelling(false); }} onOk={() => cancelForm.submit()}><p>A justificativa fica no histórico interno. O cancelamento depende de confirmação do município e não estorna o financeiro.</p><Form form={cancelForm} layout="vertical" onFinish={v => execute('cancelar', v.justificativa)}><Form.Item name="justificativa" label="Justificativa" rules={required}><Input.TextArea maxLength={500} rows={3} /></Form.Item></Form></Modal>
  </>;
}
