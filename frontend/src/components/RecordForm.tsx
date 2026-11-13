import { Alert, Col, DatePicker, Form, Input, InputNumber, Row, Select, Switch, Typography } from 'antd';
import type { FormInstance } from 'antd';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';
import { api } from '../api';
import { useSession } from '../session';
import type { Page, Resource } from '../types';
import { RemoteSelect } from './RemoteSelect';
const OPTIONS = '/clientes/api/opcoes/?tipo=';
const required = [{ required: true, message: 'Preencha este campo.' }];
const switches = [ ['libera_tcm', 'TCM'], ['libera_pagonline', 'Pagamento online'], ['libera_sistema', 'Sistema'], ['libera_transparencia', 'Transparência'], ['libera_contracheque', 'Contracheque'], ['gerar_notas', 'Geração de notas'] ];
function validDocument(value: string, cpf: boolean) {
  const digits = value.replace(/\D/g, '');
  if (digits.length !== (cpf ? 11 : 14) || new Set(digits).size === 1) return false;
  const numbers = digits.split('').map(Number), length = cpf ? 9 : 12;
  for (let j = length; j < length + 2; j++) {
    let sum = 0;
    for (let i = 0; i < j; i++) sum += numbers[i] * (cpf ? j + 1 - i : (j - i - 1) % 8 + 2);
    const digit = sum % 11 < 2 ? 0 : 11 - sum % 11;
    if (digit !== numbers[j]) return false;
  }
  return true;
}
const documentRule = (cpf: boolean) => ({ validator: (_: unknown, value: string) => !value || validDocument(value, cpf) ? Promise.resolve() : Promise.reject(new Error(cpf ? 'CPF inválido.' : 'CNPJ inválido.')) });
function DateField({ name, label, mandatory = false }: { name: string; label: string; mandatory?: boolean }) {
  return <Form.Item name={name} label={label} rules={mandatory ? required : []}
    getValueProps={value => ({ value: value ? dayjs(value) : null })}
    normalize={value => value?.format('YYYY-MM-DD') ?? null}><DatePicker format="DD/MM/YYYY" style={{ width: '100%' }} /></Form.Item>;
}
export function RecordForm({ resource, form, editing }: { resource: Resource; form: FormInstance; editing: boolean }) {
  const { user } = useSession();
  const uf = Form.useWatch('uf', form) as number | undefined;
  const [states, setStates] = useState<{ value: number; label: string }[]>([]);
  const [stateIssue, setStateIssue] = useState(false);
  useEffect(() => {
    api<Page<{ id: number; sigla: string; descricao: string }>>('/clientes/api/ufs/?page_size=200')
      .then(page => setStates(page.results.map(s => ({ value: s.id, label: `${s.sigla} — ${s.descricao}` }))))
      .catch(() => setStateIssue(true));
  }, []);
  if (resource === 'liberacoes') return <><Alert type="info" title="A chave é gerada ao salvar a liberação." showIcon style={{ marginBottom: 24 }} /><Form.Item name="cliente" label="Cliente" rules={required}><RemoteSelect url={OPTIONS + 'clientes'} placeholder="Busque o cliente" /></Form.Item><Row gutter={16}><Col span={12}><Form.Item name="competencia" label="Competência" rules={required}><Select options={Array.from({ length: 12 }, (_, i) => ({ value: String(i + 1).padStart(2, '0'), label: dayjs().month(i).format('MMMM') }))} /></Form.Item></Col><Col span={12}><Form.Item name="exercicio" label="Exercício" rules={required}><InputNumber min={1} max={9999} style={{ width: '100%' }} /></Form.Item></Col></Row></>;
  if (resource === 'bloqueios') return <><Form.Item name="cliente" label="Cliente" rules={required}><RemoteSelect url={OPTIONS + 'clientes'} /></Form.Item><Row gutter={16}><Col span={12}><DateField name="dt_ate" label="Data inicial" mandatory /></Col><Col span={12}><DateField name="dt_aparte" label="Data final" mandatory /></Col></Row><Form.Item noStyle shouldUpdate>{() => { const start = form.getFieldValue('dt_ate'), end = form.getFieldValue('dt_aparte'); return start && end && end < start ? <Alert type="warning" title="A data final deve ser igual ou posterior à inicial." style={{ marginBottom: 16 }} /> : null; }}</Form.Item><SwitchFields /><Form.Item name="desativar" label="Desativar cliente no período" valuePropName="checked"><Switch /></Form.Item></>;
  const partner = resource === 'parceiros';
  const text = (name: string, label: string, maxLength: number, mandatory = false) => <Form.Item name={name} label={label} rules={mandatory ? required : []}><Input maxLength={maxLength} /></Form.Item>;
  return <>
    <Typography.Title level={5}>Identificação</Typography.Title>
    {text('instituicao', 'Instituição', 200, true)}
    <Row gutter={16}><Col xs={24} sm={8}><Form.Item name="tipo_pessoa" label="Tipo de pessoa"><Select options={[{ value: 'PJ', label: 'Pessoa jurídica' }, { value: 'PF', label: 'Pessoa física' }]} /></Form.Item></Col><Col xs={24} sm={16}><Form.Item name="cnpj" label="CNPJ" rules={[...required, documentRule(false)]}><Input maxLength={20} placeholder="00.000.000/0000-00" /></Form.Item></Col></Row>
    {!partner && <Form.Item name="parceiro" label="Parceiro"><RemoteSelect url={OPTIONS + 'parceiros'} placeholder="Sem parceiro" /></Form.Item>}
    {text('gcf', 'Inscrição estadual / CGF', 20)}
    <Typography.Title level={5}>Endereço</Typography.Title>
    {text('endereco', 'Endereço', partner ? 60 : 100, true)}
    <Row gutter={16}><Col span={8}>{text('numero', 'Número', 10, true)}</Col><Col span={16}>{text('bairro', 'Bairro', 60, true)}</Col></Row>
    {stateIssue && <Alert type="error" title="Não foi possível carregar as UFs. Feche e abra o formulário para tentar novamente." />}
    <Row gutter={16}><Col span={8}><Form.Item name="uf" label="UF" rules={required}><Select options={states} disabled={!!user?.uf} onChange={() => form.setFieldValue('cidade', null)} showSearch optionFilterProp="label" /></Form.Item></Col><Col span={16}><Form.Item name="cidade" label="Município" rules={partner ? required : []}><RemoteSelect url={'/clientes/api/municipios/?uf=' + (uf ?? '')} labelField="descricao" disabled={!uf} /></Form.Item></Col></Row>
    <Row gutter={16}><Col span={8}>{text('cep', 'CEP', 15, true)}</Col><Col span={16}>{text('site', 'Site', 200)}</Col></Row>
    <Typography.Title level={5}>Responsável e contato</Typography.Title>
    {text('resp_nome', 'Nome do responsável', 60)}
    <Row gutter={16}><Col span={12}>{text('resp_cargo', 'Cargo', partner ? 60 : 100)}</Col><Col span={12}><Form.Item name="resp_cpf" label="CPF do responsável" rules={[documentRule(true)]}><Input maxLength={20} /></Form.Item></Col></Row>
    <Row gutter={16}><Col span={12}><DateField name="dt_resp_nascimento" label="Nascimento" /></Col><Col span={12}>{text('resp_telefone', 'Telefone', 20)}</Col></Row>
    <Form.Item name="resp_email" label="E-mail" rules={partner ? [{ type: 'email', message: 'Informe um e-mail válido.' }] : []}><Input maxLength={partner ? 100 : 200} placeholder={partner ? 'contato@empresa.com.br' : 'Para vários contatos, separe por vírgula'} /></Form.Item>
    {partner ? <><Typography.Title level={5}>Condições do parceiro</Typography.Title><Form.Item name="excecao" label="Exceção nas liberações" valuePropName="checked"><Switch /></Form.Item><Form.Item name="libera_clientes" label="Libera clientes" valuePropName="checked"><Switch /></Form.Item><DateField name="dt_data_limite" label="Data limite" /></> : <>
      <Typography.Title level={5}>Integrações</Typography.Title>
      <Row gutter={16}><Col span={12}>{text('codigolayout', 'Código Layout', 10)}</Col><Col span={12}><Form.Item name="codigoentidade" label="Código da entidade" rules={[{ pattern: /^\d{1,2}$/, message: 'Informe até dois dígitos.' }]}><Input maxLength={2} /></Form.Item></Col></Row>
      <Row gutter={16}>{[['codigosim', 'Código SIM'], ['codigoold', 'Código antigo'], ['codigotcm', 'Código TCM'], ['usertcm', 'Usuário TCM']].map(([field, label]) => <Col span={12} key={field}>{text(field, label, 10)}</Col>)}</Row>
      <Form.Item name="senhatcm" label="Senha TCM" extra={editing ? 'Deixe em branco para manter a senha atual.' : undefined}><Input.Password maxLength={10} autoComplete="new-password" /></Form.Item>
      <Typography.Title level={5}>Dados bancários</Typography.Title>
      <Form.Item name="banco" label="Banco"><RemoteSelect url="/clientes/api/bancos/" labelField="descricao" /></Form.Item>
      <Row gutter={16}><Col span={12}>{text('agencia', 'Agência', 10)}</Col><Col span={12}>{text('numero_conta', 'Número da conta', 15)}</Col></Row>
      <Typography.Title level={5}>Situação e acessos</Typography.Title><Row gutter={16}><Col span={12}><Form.Item name="ativo" label="Ativo" valuePropName="checked"><Switch /></Form.Item></Col><Col span={12}><Form.Item name="desativar" label="Desativado" valuePropName="checked"><Switch /></Form.Item></Col></Row><SwitchFields />
      <Form.Item name="observacoes" label="Observações"><Input.TextArea rows={3} /></Form.Item>
    </>}
  </>;
}
function SwitchFields() { return <Row gutter={16}>{switches.map(([field, label]) => <Col span={12} key={field}><Form.Item name={field} label={label} valuePropName="checked"><Switch /></Form.Item></Col>)}</Row>; }
