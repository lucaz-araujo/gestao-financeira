import { useEffect, useState } from 'react';
import { Alert, App, Button, Drawer, Form, Input, Select, Space, Tag } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { Table } from '../components/DataTable';
import { api, errorMessage } from '../api';
import { useSession } from '../session';
import type { Page } from '../types';
interface UserRow { id: number; username: string; first_name: string; last_name: string; email: string; is_active: boolean; empresas_nomes: { id: number; razao: string }[] }
interface Options { empresas: { id: number; razao: string }[]; permissoes: { id: number; codigo: string; modulo: string; nome: string }[]; uf: number | null }
const endpoint = '/usuario/api/usuarios/';
const modules: Record<string, string> = { agenda: 'Contatos', chaves: 'Chaves', clientes: 'Clientes e parceiros', compras: 'Compras', configambiente: 'Ambiente fiscal', conta: 'Contas e bancos', contabil: 'Contábil', contratos: 'Contratos', empresa: 'Empresas', financeiro: 'Financeiro', notas: 'Notas fiscais', produtos: 'Produtos', recadclientes: 'Recadastramento', servicos: 'Serviços' };
export function Users() {
  const { empresa, can } = useSession(); const { message } = App.useApp(); const [form] = Form.useForm();
  const [data, setData] = useState<Page<UserRow>>({ count: 0, results: [], next: null, previous: null });
  const [options, setOptions] = useState<Options>();
  const [page, setPage] = useState(1), [search, setSearch] = useState(''), [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(false), [saving, setSaving] = useState(false), [open, setOpen] = useState(false);
  const [error, setError] = useState(''), [saveError, setSaveError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    api<Options>(endpoint + 'opcoes/', { signal: controller.signal }, empresa).then(setOptions).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); });
    return () => controller.abort();
  }, [empresa]);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    const timer = setTimeout(() => {
      api<Page<UserRow>>(endpoint + '?' + new URLSearchParams({ page: String(page), search }), { signal: controller.signal }, empresa)
        .then(setData).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, search ? 250 : 0);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [empresa, page, search, reload]);
  async function save(values: Record<string, unknown>) {
    setSaving(true); setSaveError('');
    try {
      await api(endpoint, { method: 'POST', body: JSON.stringify(values) }, empresa);
      form.resetFields(); setOpen(false); setPage(1); setReload(value => value + 1);
      void message.success('Usuário cadastrado. O acesso segue as empresas e permissões selecionadas.');
    } catch (e) { setSaveError(errorMessage(e)); } finally { setSaving(false); }
  }
  const groups = [...new Set(options?.permissoes.map(permission => permission.modulo) ?? [])].map(modulo => ({ label: modules[modulo] ?? modulo, options: options!.permissoes.filter(permission => permission.modulo === modulo).map(permission => ({ value: permission.id, label: permission.nome, title: permission.codigo })) }));
  return <><div className="page-heading"><div><div className="eyebrow">ACESSOS / USUÁRIOS</div><h1>Cadastro de usuário</h1><p>Cadastre contas com acesso somente às empresas e aos módulos autorizados.</p></div>{can('usuario.add_usuario') && <Button type="primary" icon={<PlusOutlined/>} aria-label="Novo usuário" disabled={!options?.empresas.length} onClick={() => { form.resetFields(); form.setFieldsValue({ empresas: empresa ? [empresa] : [], permissoes: [] }); setSaveError(''); setOpen(true); }}>Novo usuário</Button>}</div>
    <Alert type="info" showIcon title="Acesso limitado por empresa" description="A lista mostra contas comuns da empresa ativa cujos vínculos estão integralmente no seu escopo. Contas administrativas são gerenciadas pelo administrador." style={{ marginBottom: 20 }}/>
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 20 }}/>}
    <section className="table-panel"><div className="table-toolbar"><Input aria-label="Buscar usuário" placeholder="Nome, usuário ou e-mail" value={search} allowClear onChange={event => { setSearch(event.target.value); setPage(1); }} style={{ maxWidth: 340 }}/><Button icon={<ReloadOutlined/>} aria-label="Atualizar usuários" loading={loading} onClick={() => setReload(value => value + 1)}/></div>
      <Table<UserRow> exportTitle="Cadastro de usuário" rowKey="id" loading={loading} dataSource={data.results} scroll={{ x: 800 }} pagination={{ current: page, pageSize: 25, total: data.count, showSizeChanger: false, onChange: setPage }} columns={[
        { title: 'Usuário', dataIndex: 'username' }, { title: 'Nome', render: (_, row) => [row.first_name, row.last_name].filter(Boolean).join(' ') || '—' },
        { title: 'E-mail', dataIndex: 'email' }, { title: 'Empresas autorizadas', render: (_, row) => row.empresas_nomes.map(company => company.razao).join(', ') },
        { title: 'Situação', dataIndex: 'is_active', render: active => <Tag>{active ? 'Ativo' : 'Inativo'}</Tag> },
      ]}/>
    </section>
    <Drawer title="Novo usuário" open={open} size={640} destroyOnHidden maskClosable={!saving} onClose={() => { if (!saving) { setOpen(false); form.resetFields(); } }}>
      {saveError && <Alert type="error" showIcon title={saveError} style={{ marginBottom: 20 }}/>}
      <Form form={form} layout="vertical" onFinish={save}>
        <Form.Item name="username" label="Nome de usuário" rules={[{ required: true, message: 'Informe o usuário.' }, { pattern: /^[\w.@+-]+$/, message: 'Use letras, números ou @ . + - _.' }]}><Input maxLength={15} autoComplete="off"/></Form.Item>
        <Space align="start" wrap><Form.Item name="first_name" label="Nome" rules={[{ required: true, message: 'Informe o nome.' }]}><Input maxLength={30}/></Form.Item><Form.Item name="last_name" label="Sobrenome"><Input maxLength={30}/></Form.Item></Space>
        <Form.Item name="email" label="E-mail" rules={[{ required: true, message: 'Informe o e-mail.' }, { type: 'email', message: 'E-mail inválido.' }]}><Input maxLength={255} autoComplete="off"/></Form.Item>
        <Form.Item name="empresas" label="Empresas autorizadas" rules={[{ required: true, type: 'array', min: 1, message: 'Selecione pelo menos uma empresa.' }]}><Select mode="multiple" optionFilterProp="label" options={options?.empresas.map(company => ({ value: company.id, label: company.razao }))}/></Form.Item>
        <Form.Item name="permissoes" label="Permissões nos módulos" extra="Aplicadas a todas as empresas selecionadas. Sem permissões, a conta terá apenas acesso ao próprio perfil."><Select mode="multiple" optionFilterProp="label" options={groups} placeholder="Selecione as operações permitidas"/></Form.Item>
        {!!options?.uf && <Alert type="info" title="A restrição por UF da sua conta também será aplicada ao novo usuário." style={{ marginBottom: 20 }}/>}
        <Form.Item name="password" label="Senha inicial" rules={[{ required: true, message: 'Informe a senha inicial.' }, { min: 12, message: 'Use pelo menos 12 caracteres.' }]}><Input.Password maxLength={256} autoComplete="new-password"/></Form.Item>
        <Form.Item name="conf_password" label="Confirmar senha inicial" dependencies={['password']} rules={[{ required: true, message: 'Confirme a senha.' }, ({ getFieldValue }) => ({ validator: async (_, value) => { if (value !== getFieldValue('password')) throw new Error('As senhas não conferem.'); } })]}><Input.Password maxLength={256} autoComplete="new-password"/></Form.Item>
        <Button type="primary" htmlType="submit" loading={saving} aria-label="Cadastrar usuário">Cadastrar usuário</Button>
      </Form>
    </Drawer>
  </>;
}
