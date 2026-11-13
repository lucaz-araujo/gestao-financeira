import { DeleteConfirmation } from '../components/DeleteConfirmation';
import { Table } from '../components/DataTable';
import { Alert, App, Button, Drawer, Empty, Form, Input, Popconfirm, Select, Space, Tag, Typography } from 'antd';
import { DeleteOutlined, EditOutlined, EyeOutlined, PlusOutlined, ReloadOutlined, SearchOutlined, CopyOutlined } from '@ant-design/icons';
import { useEffect, useRef, useState } from 'react';
import dayjs from 'dayjs';
import { api, ApiError, errorMessage } from '../api';
import { useSession } from '../session';
import type { Page, Resource, Row } from '../types';
import { RecordForm } from '../components/RecordForm';
import { RemoteSelect } from '../components/RemoteSelect';
import { Details } from '../components/Details';
import { ProdutoForm } from '../components/ProdutoForm';
const configs = {
  produtos: { title: 'Produtos', single: 'produto', description: 'Produtos e serviços organizados para os contratos da sua empresa.', model: 'produto' },
  clientes: { title: 'Clientes', single: 'cliente', description: 'Todos os relacionamentos da sua empresa, em um só lugar.', model: 'cliente' },
  parceiros: { title: 'Parceiros', single: 'parceiro', description: 'Conexões que ampliam o alcance do seu negócio.', model: 'parceiro' },
  liberacoes: { title: 'Liberações', single: 'liberação', description: 'Gerencie as competências e o acesso aos sistemas.', model: 'liberacao' },
  bloqueios: { title: 'Bloqueios', single: 'bloqueio', description: 'Controle os acessos e as condições de cada período.', model: 'liberacaodatas' },
};
const formatDate = (value: unknown) => typeof value === 'string' && value ? dayjs(value).format('DD/MM/YYYY') : '—';
export function ResourcePage({ resource }: { resource: Resource }) {
  const config = configs[resource];
  const { empresa, can, user } = useSession();
  const { message } = App.useApp();
  const [data, setData] = useState<Page<Row>>({ count: 0, results: [], next: null, previous: null });
  const [page, setPage] = useState(1), [pageSize, setPageSize] = useState(20), [search, setSearch] = useState('');
  const [clientFilter, setClientFilter] = useState<number>(), [status, setStatus] = useState<string>();
  const [loading, setLoading] = useState(false), [error, setError] = useState(''), [reload, setReload] = useState(0);
  const [editor, setEditor] = useState<Row | 'new' | null>(null), [detail, setDetail] = useState<Row | null>(null);
  const [saving, setSaving] = useState(false), [formError, setFormError] = useState('');
  const [form] = Form.useForm();
  const editorGeneration = useRef(0);
  const catalog = resource === 'produtos';
  const namespace = catalog ? 'produtos' : 'clientes';
  const url = catalog ? '/produtos/api/produtos/' : '/clientes/api/' + resource + '/';
  const releases = resource === 'liberacoes', registration = resource === 'clientes' || resource === 'parceiros';
  const canCreate = can(releases ? 'financeiro.add_recreceita' : `${namespace}.add_${config.model}`);
  const canEdit = !releases && can(`${namespace}.change_${config.model}`);
  const canDelete = can(`${namespace}.delete_${config.model}`);
  const refresh = () => setReload(x => x + 1);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setLoading(true); setError('');
    const timer = setTimeout(() => {
      const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (search) query.set('search', search);
      if (catalog && status) query.set('tipo_produto', status);
      if (clientFilter) query.set('cliente', String(clientFilter));
      if (status && resource === 'clientes') { query.set('desativar', status === 'disabled' ? 'true' : 'false'); if (status !== 'disabled') query.set('ativo', status === 'active' ? 'true' : 'false'); }
      api<Page<Row>>(url + '?' + query, { signal: controller.signal }, empresa).then(result => { if (active) setData(result); })
        .catch(e => { if (active) setError(errorMessage(e)); }).finally(() => { if (active) setLoading(false); });
    }, search ? 250 : 0);
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [url, page, pageSize, search, clientFilter, status, reload, empresa, resource]);
  function openEditor(row: Row | 'new') {
    editorGeneration.current++;
    form.resetFields(); setFormError(''); setEditor(row);
    const defaults = catalog ? { tipo_produto: 'P' } : registration ? { tipo_pessoa: 'PJ', uf: user?.uf, ativo: true, libera_tcm: true, libera_pagonline: true, libera_sistema: true, libera_transparencia: true, libera_contracheque: true, gerar_notas: true, libera_clientes: true, desativar: false, excecao: false } : releases ? { competencia: dayjs().format('MM'), exercicio: dayjs().year(), cliente: clientFilter } : { cliente: clientFilter, libera_tcm: false, libera_pagonline: false, libera_sistema: false, libera_transparencia: false, libera_contracheque: false, gerar_notas: false, desativar: false };
    // O drawer é montado antes de preencher o formulário via efeito abaixo.
    pendingValues.current = row === 'new' ? defaults : row;
  }
  const pendingValues = useRef<Record<string, unknown>>({});
  useEffect(() => { if (editor) form.setFieldsValue(pendingValues.current); }, [editor, form]);
  async function save(values: Record<string, unknown>) {
    const generation = editorGeneration.current;
    if (!editor) return;
    if (resource === 'bloqueios' && String(values.dt_aparte) < String(values.dt_ate)) { form.setFields([{ name: 'dt_aparte', errors: ['A data final deve ser igual ou posterior à inicial.'] }]); return; }
    if (!values.senhatcm) delete values.senhatcm;
    setSaving(true); setFormError('');
    try {
      await api(url + (editor === 'new' ? '' : editor.id + '/'), { method: editor === 'new' ? 'POST' : 'PATCH', body: JSON.stringify(values) }, empresa);
      if (editorGeneration.current !== generation) return;
      setEditor(null); refresh(); void message.success('Cadastro salvo com sucesso.');
    } catch (e) {
      if (editorGeneration.current !== generation) return;
      if (e instanceof ApiError && e.status === 400) {
        form.setFields(Object.entries(e.data).filter(([name]) => name !== 'non_field_errors').map(([name, errors]) => ({ name, errors: Array.isArray(errors) ? errors.map(String) : [String(errors)] })));
      }
      setFormError(errorMessage(e));
    } finally { if (editorGeneration.current === generation) setSaving(false); }
  }
  async function remove(row: Row) {
    try { await api(url + row.id + '/', { method: 'DELETE' }, empresa); if (data.results.length === 1 && page > 1) setPage(page - 1); else refresh(); void message.success('Registro excluído.'); }
    catch (e) { void message.error(errorMessage(e)); }
  }
  async function regenerate(row: Row) {
    try { await api(url + row.id + '/atualizar_chave/', { method: 'POST' }, empresa); refresh(); void message.success('Chave atualizada.'); }
    catch (e) { void message.error(errorMessage(e)); }
  }
  const primaryColumns = catalog ? [
    { title: 'Descrição', dataIndex: 'descricao', render: (text: string, row: Row) => <button className="record-title" onClick={() => setDetail(row)}>{text}</button> },
    { title: 'Sigla', dataIndex: 'sigla', render: (value: string) => <span className="mono">{value || '—'}</span> },
    { title: 'Tipo', dataIndex: 'tipo_produto', render: (value: string) => <Tag color={value === 'S' ? 'red' : 'default'}>{value === 'S' ? 'Serviço' : 'Produto'}</Tag> },
    { title: 'Valor', dataIndex: 'valor', render: (value: string | null) => value == null ? '—' : Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) },
  ] : registration ? [
    { title: 'Instituição', dataIndex: 'instituicao', render: (text: string, row: Row) => <button className="record-title" onClick={() => setDetail(row)}>{text}</button> },
    { title: 'CNPJ', dataIndex: 'cnpj', render: (v: string) => <span className="mono muted">{v || '—'}</span> },
    { title: 'Contato', dataIndex: 'resp_nome', render: (v: string) => v || '—', responsive: ['lg'] as ('lg')[] },
    ...(resource === 'clientes' ? [{ title: 'Situação', render: (_: unknown, row: Row) => <Tag color={row.desativar || !row.ativo ? 'default' : 'red'}>{row.desativar ? 'Desativado' : row.ativo ? 'Ativo' : 'Inativo'}</Tag> }] : []),
  ] : [
    { title: 'Cliente', render: (_: unknown, row: Row) => <span className="record-name">{String(row.cliente_nome ?? 'Cliente não disponível')}</span> },
    ...(releases ? [
      { title: 'Competência', render: (_: unknown, row: Row) => <span className="mono">{String(row.competencia)}/{String(row.exercicio)}</span> },
      { title: 'Liberado em', dataIndex: 'dt_liberacao', render: formatDate },
      { title: 'Chave', dataIndex: 'chave', render: (value: string) => <Typography.Text className="mono" copyable={{ text: value, icon: <CopyOutlined /> }}>{value.slice(0, 8)}…</Typography.Text> },
    ] : [
      { title: 'Início', dataIndex: 'dt_ate', render: formatDate }, { title: 'Fim', dataIndex: 'dt_aparte', render: formatDate },
      { title: 'Sistema', dataIndex: 'libera_sistema', render: (v: boolean) => <Tag color={v ? 'default' : 'red'}>{v ? 'Liberado' : 'Bloqueado'}</Tag> },
    ]),
  ];
  const columns = [...primaryColumns, { title: 'Ações', key: 'actions', width: 145, render: (_: unknown, row: Row) => <Space size={0}>
    <Button type="text" aria-label={`Ver ${config.single}`} icon={<EyeOutlined />} onClick={() => setDetail(row)} />
    {canEdit && <Button type="text" aria-label={`Editar ${config.single}`} icon={<EditOutlined />} onClick={() => openEditor(row)} />}
    {releases && can('clientes.change_liberacao') && <Popconfirm title="Atualizar a chave com os códigos atuais?" onConfirm={() => regenerate(row)}><Button type="text" aria-label="Atualizar chave" icon={<ReloadOutlined />} /></Popconfirm>}
    {canDelete && <DeleteConfirmation recordName={String(row.instituicao ?? row.descricao ?? row.cliente_nome ?? `#${row.id}`)} title={`Excluir ${config.single}?`} description="Registros com vínculos serão preservados." okText="Excluir" cancelText="Cancelar" onConfirm={() => remove(row)}><Button type="text" danger aria-label={`Excluir ${config.single}`} icon={<DeleteOutlined />} /></DeleteConfirmation>}
  </Space> }];
  return <>
    <div className="page-heading"><div><div className="eyebrow">{catalog ? 'CADASTROS' : 'RELACIONAMENTOS'} / {config.title.toUpperCase()}</div><h1>{config.title}<span className="count-pill">{data.count}</span></h1><p>{config.description}</p></div>{canCreate && <Button aria-label={resource === 'liberacoes' ? 'Nova liberação' : 'Novo ' + config.single} type="primary" icon={<PlusOutlined />} onClick={() => openEditor('new')}>{resource === 'liberacoes' ? 'Nova liberação' : 'Novo ' + config.single}</Button>}</div>
    <div className="overview-strip"><span className="overview-mark">{resource === 'clientes' ? '01' : resource === 'parceiros' ? '02' : resource === 'liberacoes' ? '03' : catalog ? '05' : '04'}</span><div><strong>{config.title} da empresa selecionada</strong><p>Dados organizados. Acesso sob seu controle.</p></div><span className="overview-count">{data.count.toLocaleString('pt-BR')}<small>registros</small></span></div>
    <section className="table-panel"><div className="table-toolbar"><Space wrap>
      {registration || catalog ? <Input aria-label={catalog ? "Buscar produto" : "Buscar instituição"} placeholder={catalog ? "Buscar por descrição ou sigla" : "Buscar por instituição"} prefix={<SearchOutlined className="muted" />} value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} allowClear style={{ width: 300, maxWidth: '100%' }} /> : <div style={{ width: 300 }}><RemoteSelect url="/clientes/api/opcoes/?tipo=clientes" value={clientFilter} onChange={v => { setClientFilter(v); setPage(1); }} placeholder="Filtrar por cliente" /></div>}
      {catalog && <Select aria-label="Filtrar tipo" placeholder="Todos os tipos" allowClear value={status} onChange={v => { setStatus(v); setPage(1); }} options={[{ value: 'P', label: 'Produtos' }, { value: 'S', label: 'Serviços' }]} style={{ width: 180 }} />}
      {resource === 'clientes' && <Select aria-label="Filtrar situação" placeholder="Todas as situações" allowClear value={status} onChange={v => { setStatus(v); setPage(1); }} options={[{ value: 'active', label: 'Ativos' }, { value: 'inactive', label: 'Inativos' }, { value: 'disabled', label: 'Desativados' }]} style={{ width: 180 }} />}
    </Space><Button icon={<ReloadOutlined />} aria-label="Atualizar lista" onClick={refresh} loading={loading} /></div>
    {error ? <Alert type="error" title={error} showIcon action={<Button onClick={refresh}>Tentar novamente</Button>} /> : <Table<Row> rowKey="id" columns={columns} dataSource={data.results} loading={loading} scroll={{ x: 760 }}
      locale={{ emptyText: <Empty description={`Nenhum registro encontrado em ${config.title.toLowerCase()}.`} /> }}
      pagination={{ current: page, pageSize, total: data.count, showSizeChanger: true, pageSizeOptions: [20, 50, 100], showTotal: total => `${total} registros`, onChange: (p, size) => { setPage(size !== pageSize ? 1 : p); setPageSize(size); } }} />}
    </section>
    <Drawer title={`${editor === 'new' ? 'Novo cadastro' : 'Editar cadastro'} · ${config.title}`} open={!!editor} size={760} destroyOnHidden maskClosable={!saving} onClose={() => { if (!saving) { editorGeneration.current++; setEditor(null); } }} footer={<Space style={{ float: 'right' }}><Button disabled={saving} onClick={() => setEditor(null)}>Cancelar</Button><Button aria-label="Salvar cadastro" type="primary" loading={saving} onClick={() => form.submit()}>Salvar cadastro</Button></Space>}>
      {formError && <Alert role="alert" type="error" title={formError} showIcon style={{ marginBottom: 20 }} />}<Form form={form} layout="vertical" requiredMark="optional" onFinish={save} scrollToFirstError>{catalog ? <ProdutoForm /> : <RecordForm resource={resource} form={form} editing={editor !== 'new'} />}</Form>
    </Drawer>
    <Details resource={resource} row={detail} onClose={() => setDetail(null)} />
  </>;
}
