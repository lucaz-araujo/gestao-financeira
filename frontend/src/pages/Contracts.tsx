import { DeleteConfirmation } from '../components/DeleteConfirmation';
import { Table } from '../components/DataTable';
import { Alert, App, Button, Drawer, Empty, Form, Input, Select, Space, Tag } from 'antd';
import { DeleteOutlined, EditOutlined, EyeOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import dayjs from 'dayjs';
import { api, ApiError, errorMessage } from '../api';
import { useSession } from '../session';
import type { Page } from '../types';
import type { Contract } from '../contractTypes';
import { money } from '../contractTypes';
import { ContractForm, contractOptions } from '../components/ContractForm';
import { ContractDetails } from '../components/ContractDetails';
import { RemoteSelect } from '../components/RemoteSelect';
const endpoint = '/contratos/api/contratos/';
function validationFields(value: unknown, path: (string | number)[] = []): { name: (string | number)[]; errors: string[] }[] {
  if (Array.isArray(value) && value.every(v => typeof v === 'string')) return path.length && !path.includes('non_field_errors') ? [{ name: path, errors: value }] : [];
  if (value && typeof value === 'object') return Object.entries(value).flatMap(([key, nested]) => validationFields(nested, [...path, Array.isArray(value) ? Number(key) : key]));
  return [];
}
export function Contracts() {
  const { empresa, can } = useSession();
  const { message } = App.useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const [form] = Form.useForm();
  const [rows, setRows] = useState<Page<Contract>>({ count: 0, results: [], next: null, previous: null });
  const [page, setPage] = useState(1), [pageSize, setPageSize] = useState(20), [search, setSearch] = useState('');
  const [cliente, setCliente] = useState<number>(), [active, setActive] = useState<string>();
  const [reload, setReload] = useState(0), [loading, setLoading] = useState(false), [error, setError] = useState('');
  const [editor, setEditor] = useState<Contract | 'new' | null>(null), [detail, setDetail] = useState<Contract | null>(null);
  const [saving, setSaving] = useState(false), [fetching, setFetching] = useState(false), [saveError, setSaveError] = useState('');
  const generation = useRef(0), pending = useRef<Record<string, unknown>>({});
  useEffect(() => () => { generation.current++; }, []);
  useEffect(() => {
    let alive = true;
    const controller = new AbortController();
    setLoading(true); setError('');
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (search) params.set('search', search);
      if (cliente) params.set('cliente', String(cliente));
      if (active) params.set('ativo', active);
      api<Page<Contract>>(endpoint + '?' + params, { signal: controller.signal }, empresa)
        .then(result => { if (alive) setRows(result); }).catch(e => { if (alive) setError(errorMessage(e)); }).finally(() => { if (alive) setLoading(false); });
    }, search ? 250 : 0);
    return () => { alive = false; clearTimeout(timer); controller.abort(); };
  }, [empresa, page, pageSize, search, cliente, active, reload]);
  useEffect(() => { if (editor) form.setFieldsValue(pending.current); }, [editor, form]);
  useEffect(() => {
    const id = searchParams.get('imprimir');
    if (!id) return;
    let alive = true;
    api<Contract>(endpoint + encodeURIComponent(id) + '/', {}, empresa).then(value => { if (alive) setDetail(value); }).catch(e => { if (alive) void message.error(errorMessage(e)); });
    return () => { alive = false; };
  }, [searchParams, empresa, message]);
  function create() {
    form.resetFields(); setSaveError(''); generation.current++;
    pending.current = { cliente, dia_nota: 1, exercicio: dayjs().year(), ativo: true, emitirnota: true, prestacao_municipio: false,
      perc_iss: '0.00', perc_irpj: '0.00', valor_iss: '0.00', valor_irpj: '0.00', itens: [], renovacoes: [] };
    setEditor('new');
  }
  async function open(row: Contract, edit: boolean) {
    const current = ++generation.current;
    setFetching(true);
    try {
      const value = await api<Contract>(endpoint + row.id + '/', {}, empresa);
      if (current !== generation.current) return;
      if (edit) { form.resetFields(); setSaveError(''); pending.current = { ...value }; setEditor(value); }
      else setDetail(value);
    } catch (e) { void message.error(errorMessage(e)); } finally { if (current === generation.current) setFetching(false); }
  }
  async function save(values: Record<string, unknown>) {
    if (!editor) return;
    const current = generation.current;
    setSaving(true); setSaveError('');
    try {
      await api(endpoint + (editor === 'new' ? '' : editor.id + '/'), { method: editor === 'new' ? 'POST' : 'PATCH', body: JSON.stringify(values) }, empresa);
      if (current === generation.current) { setEditor(null); setReload(v => v + 1); void message.success('Contrato salvo com sucesso.'); }
    } catch (e) {
      if (current === generation.current) {
        if (e instanceof ApiError && e.status === 400) form.setFields(validationFields(e.data));
        setSaveError(errorMessage(e));
      }
    } finally { if (current === generation.current) setSaving(false); }
  }
  async function remove(row: Contract) {
    try {
      await api(endpoint + row.id + '/', { method: 'DELETE' }, empresa);
      if (rows.results.length === 1 && page > 1) setPage(page - 1); else setReload(v => v + 1);
      void message.success('Contrato excluído.');
    } catch (e) { void message.error(errorMessage(e)); }
  }
  return <>
    <div className="page-heading"><div><div className="eyebrow">GESTÃO / CONTRATOS</div><h1>Contratos<span className="count-pill">{rows.count}</span></h1><p>Vigência, produtos, valores e renovações da sua empresa.</p></div><Space wrap><Link to="/relatorios?tipo=CON_S"><Button>Relatório de contratos</Button></Link>{can('contratos.add_contrato') && <Button aria-label="Novo contrato" type="primary" icon={<PlusOutlined />} onClick={create}>Novo contrato</Button>}</Space></div>
    <div className="overview-strip"><span className="overview-mark">06</span><div><strong>Contratos da empresa selecionada</strong><p>Itens e renovações salvos juntos, com o histórico fiscal preservado.</p></div><span className="overview-count">{rows.count}<small>registros</small></span></div>
    <section className="table-panel"><div className="table-toolbar"><Space wrap><Input aria-label="Buscar contrato" placeholder="Buscar número ou cliente" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} allowClear style={{ width: 260 }} /><div style={{ width: 230 }}><RemoteSelect url={contractOptions + 'clientes'} value={cliente} onChange={value => { setCliente(value); setPage(1); }} placeholder="Filtrar por cliente" /></div><Select aria-label="Situação do contrato" placeholder="Todas as situações" value={active} onChange={value => { setActive(value); setPage(1); }} allowClear style={{ width: 170 }} options={[{ value: 'true', label: 'Ativos' }, { value: 'false', label: 'Inativos' }]} /></Space><Button aria-label="Atualizar contratos" icon={<ReloadOutlined />} loading={loading} onClick={() => setReload(v => v + 1)} /></div>
    {error ? <Alert type="error" title={error} showIcon action={<Button onClick={() => setReload(v => v + 1)}>Tentar novamente</Button>} /> : <Table<Contract> rowKey="id" loading={loading || fetching} dataSource={rows.results} scroll={{ x: 900 }} locale={{ emptyText: <Empty description="Nenhum contrato encontrado." /> }} columns={[
      { title: 'Contrato', dataIndex: 'numero', render: (value, row) => <button className="record-title" onClick={() => open(row, false)}>{value || 'Sem número'}</button> },
      { title: 'Cliente', dataIndex: 'cliente_nome' }, { title: 'Fim da vigência', dataIndex: 'dt_data_final', render: value => value ? dayjs(value).format('DD/MM/YYYY') : '—' },
      { title: 'Valor líquido', dataIndex: 'valor_liquido', render: money }, { title: 'Situação', dataIndex: 'ativo', render: value => <Tag color={value ? 'red' : 'default'}>{value ? 'Ativo' : 'Inativo'}</Tag> },
      { title: 'Ações', width: 150, render: (_, row) => <Space size={0}><Button type="text" aria-label="Ver contrato" icon={<EyeOutlined />} onClick={() => open(row, false)} />{can('contratos.change_contrato') && <Button type="text" aria-label="Editar contrato" icon={<EditOutlined />} onClick={() => open(row, true)} />}{can('contratos.delete_contrato') && <DeleteConfirmation recordName={String(row.numero ?? row.cliente_nome ?? `#${row.id}`)} title="Excluir contrato e seus itens e renovações?" description="Contratos com notas vinculadas serão preservados." okText="Excluir" cancelText="Cancelar" onConfirm={() => remove(row)}><Button type="text" danger aria-label="Excluir contrato" icon={<DeleteOutlined />} /></DeleteConfirmation>}</Space> },
    ]} pagination={{ current: page, pageSize, total: rows.count, showSizeChanger: true, pageSizeOptions: [20, 50, 100], onChange: (next, size) => { setPage(size !== pageSize ? 1 : next); setPageSize(size); } }} />}
    </section>
    <Drawer title={editor === 'new' ? 'Novo contrato' : 'Editar contrato'} open={!!editor} size={900} destroyOnHidden maskClosable={!saving} onClose={() => { if (!saving) setEditor(null); }} footer={<Space style={{ float: 'right' }}><Button disabled={saving} onClick={() => setEditor(null)}>Cancelar</Button><Button aria-label="Salvar contrato" type="primary" loading={saving} onClick={() => form.submit()}>Salvar contrato</Button></Space>}>
      {saveError && <Alert type="error" title={saveError} showIcon style={{ marginBottom: 20 }} />}<Form form={form} layout="vertical" onFinish={save} scrollToFirstError><ContractForm form={form} hasNotes={editor !== 'new' && !!editor?.tem_nota} /></Form>
    </Drawer>
    <ContractDetails value={detail} close={() => { setDetail(null); if (searchParams.has('imprimir')) setSearchParams({}); }} />
  </>;
}
