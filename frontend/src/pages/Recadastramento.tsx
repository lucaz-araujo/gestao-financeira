import { DeleteConfirmation } from '../components/DeleteConfirmation';
import { Table } from '../components/DataTable';
import { useEffect, useState } from 'react';
import { Alert, App, Button, Descriptions, Drawer, Empty, Form, Input, Space, Tabs } from 'antd';
import { api, errorMessage } from '../api';
import { RemoteSelect } from '../components/RemoteSelect';
import { useSession } from '../session';
import type { Page, Row } from '../types';

export const recadResources = [
  { key: 'entidades', label: 'Entidades', model: 'entidaderecad' },
  { key: 'usuarios', label: 'Usuários da entidade', model: 'usuariorecad' },
  { key: 'contadores', label: 'Contadores', model: 'contadorrecad' },
  { key: 'controladores', label: 'Controladores', model: 'controladorrecad' },
  { key: 'prefeitos', label: 'Prefeitos', model: 'prefeitorecad' },
  { key: 'vice-prefeitos', label: 'Vice-prefeitos', model: 'viceprefeitorecad' },
] as const;
type Resource = typeof recadResources[number];
const options = '/recadclientes/api/opcoes/';
const required = [{ required: true, whitespace: true, message: 'Informe o nome.' }];

export function Recadastramento() {
  const { can } = useSession();
  const visible = recadResources.filter(resource => can('recadclientes.view_' + resource.model));
  const [selected, setSelected] = useState<string>(visible[0]?.key ?? '');
  const resource = visible.find(value => value.key === selected) ?? visible[0];
  return <><div className="page-heading"><div><div className="eyebrow">RELACIONAMENTO / RECADASTRAMENTO</div><h1>Recadastramento</h1><p>Mantenha as entidades e os contatos dos responsáveis vinculados aos clientes da empresa ativa.</p></div></div>
    {resource ? <><Tabs activeKey={resource.key} onChange={setSelected} items={visible.map(value => ({ key: value.key, label: value.label }))}/><RecadResource key={resource.key} resource={resource}/></> : <Empty description="Sua conta não possui acesso ao recadastramento."/>}
  </>;
}

function RecadResource({ resource }: { resource: Resource }) {
  const { empresa, can } = useSession(), { message } = App.useApp(), [form] = Form.useForm();
  const entity = resource.key === 'entidades', endpoint = '/recadclientes/api/' + resource.key + '/';
  const parent = entity ? 'cliente' : 'entidade', parentLabel = entity ? 'Cliente' : 'Entidade';
  const parentOptions = options + '?tipo=' + (entity ? 'clientes' : 'entidades');
  const uf = Form.useWatch('uf', form);
  const [data, setData] = useState<Page<Row>>({ count: 0, results: [], next: null, previous: null });
  const [page, setPage] = useState(1), [search, setSearch] = useState(''), [filter, setFilter] = useState<number>(), [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(false), [error, setError] = useState('');
  const [editor, setEditor] = useState<Row | 'new' | null>(null), [detail, setDetail] = useState<Row | null>(null);
  const [saving, setSaving] = useState(false), [saveError, setSaveError] = useState('');
  const permission = (verb: string) => can('recadclientes.' + verb + '_' + resource.model);
  useEffect(() => {
    let active = true; const controller = new AbortController();
    setLoading(true); setError('');
    const timer = setTimeout(() => {
      const query = new URLSearchParams({ page: String(page), search }); if (filter) query.set(parent, String(filter));
      api<Page<Row>>(endpoint + '?' + query, { signal: controller.signal }, empresa).then(value => { if (active) setData(value); })
        .catch(e => { if (active) setError(errorMessage(e)); }).finally(() => { if (active) setLoading(false); });
    }, 200);
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [endpoint, empresa, page, search, filter, parent, reload]);
  async function edit(row: Row | 'new') {
    setSaveError('');
    try {
      const value = row === 'new' ? 'new' : await api<Row>(endpoint + row.id + '/', {}, empresa);
      form.resetFields(); form.setFieldsValue(value === 'new' ? { [parent]: filter } : value);
      setEditor(value);
    }
    catch (e) { void message.error(errorMessage(e)); }
  }
  async function save(values: Record<string, unknown>) {
    if (!editor) return;
    setSaving(true); setSaveError('');
    try { await api(endpoint + (editor === 'new' ? '' : editor.id + '/'), { method: editor === 'new' ? 'POST' : 'PATCH', body: JSON.stringify(values) }, empresa); setEditor(null); setReload(value => value + 1); void message.success('Cadastro salvo.'); }
    catch (e) { setSaveError(errorMessage(e)); } finally { setSaving(false); }
  }
  async function remove(row: Row) {
    try { await api(endpoint + row.id + '/', { method: 'DELETE' }, empresa); if (data.results.length === 1 && page > 1) setPage(page - 1); else setReload(value => value + 1); void message.success('Cadastro excluído.'); }
    catch (e) { void message.error(errorMessage(e)); }
  }
  const fields = entity
    ? [['nome', 'Nome da entidade'], ['cliente_nome', 'Cliente'], ['codigo', 'Código'], ['tipo', 'Tipo'], ['uf_sigla', 'UF'], ['cidade_nome', 'Município'], ['telefone', 'Telefone'], ['site', 'Site'], ['email', 'E-mail']]
    : [['nome_completo', 'Nome completo'], ['entidade_nome', 'Entidade'], ...(resource.key === 'usuarios' ? [['cargo', 'Cargo']] : []), ['telefone', 'Telefone'], ['email', 'E-mail']];
  return <>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, marginBottom: 20 }}><h2>{resource.label} <span className="count-pill">{data.count}</span></h2>{permission('add') && <Button type="primary" onClick={() => edit('new')}>Novo cadastro</Button>}</div>
    <section className="table-panel"><div className="table-toolbar"><Space wrap><Input aria-label="Buscar recadastramento" placeholder="Nome ou identificação" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}/><div style={{ width: 230 }}><RemoteSelect url={parentOptions} labelField="descricao" placeholder={'Filtrar ' + parentLabel.toLowerCase()} value={filter} onChange={value => { setFilter(value); setPage(1); }}/></div></Space><Button onClick={() => setReload(value => value + 1)}>Atualizar</Button></div>
      {error && <Alert type="error" showIcon title={error}/>}
      <Table<Row> rowKey="id" loading={loading} dataSource={data.results} scroll={{ x: 850 }} pagination={{ current: page, pageSize: 50, total: data.count, showSizeChanger: false, onChange: setPage }} columns={[
        { title: 'Nome', dataIndex: entity ? 'nome' : 'nome_completo' }, { title: parentLabel, dataIndex: parent + '_nome' }, { title: 'Telefone', dataIndex: 'telefone' }, { title: 'E-mail', dataIndex: 'email' },
        { title: 'Ações', render: (_, row) => <Space><Button onClick={() => setDetail(row)}>Ver</Button>{permission('change') && <Button onClick={() => edit(row)}>Editar</Button>}{permission('delete') && <DeleteConfirmation recordName={String(row.nome ?? row.instituicao ?? row.descricao ?? `#${row.id}`)} title="Excluir cadastro?" description={entity ? 'Entidades com responsáveis vinculados precisam ser revisadas antes da exclusão.' : undefined} okText="Excluir" cancelText="Cancelar" onConfirm={() => remove(row)}><Button danger>Excluir</Button></DeleteConfirmation>}</Space> },
      ]}/></section>
    <Drawer title={'Cadastro — ' + resource.label} open={!!editor} size={640} forceRender maskClosable={!saving} onClose={() => { if (!saving) setEditor(null); }} footer={<Button type="primary" aria-label="Salvar cadastro" loading={saving} onClick={() => form.submit()}>Salvar cadastro</Button>}>
      {saveError && <Alert type="error" showIcon title={saveError}/>}
      <Form form={form} layout="vertical" onFinish={save} requiredMark={false}>
        <Form.Item name={parent} label={parentLabel} rules={[{ required: true, message: 'Selecione ' + parentLabel.toLowerCase() + '.' }]}><RemoteSelect url={parentOptions} labelField="descricao" disabled={entity && editor !== 'new'}/></Form.Item>
        {entity && editor !== 'new' && <p>O vínculo com o cliente é definido na criação.</p>}
        <Form.Item name={entity ? 'nome' : 'nome_completo'} label={entity ? 'Nome da entidade' : 'Nome completo'} rules={required}><Input maxLength={60}/></Form.Item>
        {entity && <><Form.Item name="codigo" label="Código"><Input maxLength={4}/></Form.Item><Form.Item name="tipo" label="Tipo"><Input maxLength={4}/></Form.Item>
          <Form.Item name="uf" label="UF"><RemoteSelect url={options + '?tipo=ufs'} labelField="descricao" onChange={() => form.setFieldValue('cidade', null)}/></Form.Item>
          <Form.Item name="cidade" label="Município"><RemoteSelect url={options + '?tipo=municipios' + (uf ? '&uf=' + uf : '')} labelField="descricao" disabled={!uf}/></Form.Item>
          <Form.Item name="site" label="Site" rules={[{ type: 'url', message: 'Informe um endereço completo, incluindo https://.' }]}><Input maxLength={100} placeholder="https://"/></Form.Item></>}
        {resource.key === 'usuarios' && <Form.Item name="cargo" label="Cargo"><Input maxLength={60}/></Form.Item>}
        <Form.Item name="telefone" label="Telefone"><Input maxLength={15}/></Form.Item>
        <Form.Item name="email" label="E-mail" rules={[{ type: 'email', message: 'Informe um e-mail válido.' }]}><Input maxLength={100}/></Form.Item>
      </Form>
    </Drawer>
    <Drawer title="Detalhes do recadastramento" open={!!detail} onClose={() => setDetail(null)}>{detail && <Descriptions bordered column={1} items={fields.map(([key, label]) => ({ key, label, children: String(detail[key] ?? '—') }))}/>}</Drawer>
  </>;
}
