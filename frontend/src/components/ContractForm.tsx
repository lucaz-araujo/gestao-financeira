import { Alert, App, Button, Col, DatePicker, Form, Input, InputNumber, Row, Select, Space, Switch, Typography } from 'antd';
import type { FormInstance } from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useState } from 'react';
import { api, errorMessage } from '../api';
import { useSession } from '../session';
import { RemoteSelect } from './RemoteSelect';
const required = [{ required: true, message: 'Preencha este campo.' }];
export const contractOptions = '/contratos/api/contratos/opcoes/?tipo=';
function DateInput({ name, label }: { name: string | (string | number)[]; label: string }) {
  return <Form.Item name={name} label={label} rules={required} getValueProps={value => ({ value: value ? dayjs(value) : null })}
    normalize={value => value?.format('YYYY-MM-DD') ?? null}><DatePicker format="DD/MM/YYYY" style={{ width: '100%' }} /></Form.Item>;
}
export function ContractForm({ form, hasNotes }: { form: FormInstance; hasNotes: boolean }) {
  const { empresa } = useSession();
  const { message } = App.useApp();
  const [calculating, setCalculating] = useState(false);
  async function calculate() {
    try {
      const values = await form.validateFields(['valor_bruto', 'perc_iss', 'perc_irpj']);
      setCalculating(true);
      const result = await api<Record<string, string>>('/contratos/api/contratos/calcular/', { method: 'POST', body: JSON.stringify(values) }, empresa);
      form.setFieldsValue(result);
    } catch (error) { if (!(error && typeof error === 'object' && 'errorFields' in error)) void message.error(errorMessage(error)); }
    finally { setCalculating(false); }
  }
  return <>
    <Typography.Title level={5}>Identificação e vigência</Typography.Title>
    {hasNotes && <Alert type="info" showIcon title="Este contrato possui notas vinculadas. O cliente e os documentos fiscais já emitidos serão preservados." style={{ marginBottom: 20 }} />}
    <Form.Item name="cliente" label="Cliente" rules={required}><RemoteSelect url={contractOptions + 'clientes'} disabled={hasNotes} /></Form.Item>
    <Row gutter={16}><Col xs={24} sm={12}><Form.Item name="numero" label="Número do contrato" rules={required}><Input maxLength={20} /></Form.Item></Col><Col xs={12} sm={6}><Form.Item name="dia_nota" label="Dia da nota" rules={required}><InputNumber min={1} max={31} precision={0} style={{ width: '100%' }} /></Form.Item></Col><Col xs={12} sm={6}><Form.Item name="exercicio" label="Exercício" rules={required}><InputNumber min={1} max={9999} precision={0} style={{ width: '100%' }} /></Form.Item></Col></Row>
    <Row gutter={16}><Col span={12}><DateInput name="dt_data_contrato" label="Data do contrato" /></Col><Col span={12}><DateInput name="dt_data_final" label="Data final" /></Col></Row>
    <Form.Item name="objeto" label="Objeto" rules={required}><Input.TextArea rows={3} /></Form.Item>
    <Form.Item name="observacoes" label="Observações"><Input.TextArea rows={2} /></Form.Item>
    <Row gutter={16}><Col xs={12} sm={8}><Form.Item name="ativo" label="Ativo" valuePropName="checked"><Switch /></Form.Item></Col><Col xs={12} sm={8}><Form.Item name="emitirnota" label="Emitir nota" valuePropName="checked"><Switch /></Form.Item></Col><Col xs={24} sm={8}><Form.Item name="prestacao_municipio" label="Serviço no município" valuePropName="checked"><Switch /></Form.Item></Col></Row>
    <Typography.Title level={5}>Produtos e serviços</Typography.Title>
    <Form.List name="itens">{(fields, { add, remove }) => <>
      {fields.map(field => <section className="contract-line" key={field.key}>
        <Form.Item name={[field.name, 'id']} hidden><Input /></Form.Item>
        <Row gutter={12}><Col xs={24} sm={14}><Form.Item name={[field.name, 'produtos']} label={`Produto ${field.name + 1}`} rules={required}><RemoteSelect url={contractOptions + 'produtos'} labelField="descricao" /></Form.Item></Col><Col xs={19} sm={8}><Form.Item name={[field.name, 'valor']} label={`Valor do item ${field.name + 1}`} rules={required}><InputNumber<string> stringMode min="0" max="9999999.99999" precision={5} decimalSeparator="," prefix="R$" style={{ width: '100%' }} /></Form.Item></Col><Col xs={5} sm={2}><Button type="text" danger aria-label={`Remover item ${field.name + 1}`} icon={<DeleteOutlined />} onClick={() => remove(field.name)} style={{ marginTop: 29 }} /></Col></Row>
      </section>)}
      <Button icon={<PlusOutlined />} aria-label="Adicionar produto ao contrato" onClick={() => add({})} disabled={fields.length >= 200}>Adicionar produto</Button>
    </>}</Form.List>
    <Typography.Title level={5}>Financeiro</Typography.Title>
    <p className="muted">Os valores do contrato são informados separadamente dos itens. Use o cálculo abaixo apenas se desejar preencher os impostos pelos percentuais.</p>
    <Row gutter={16}>{[['valor_bruto', 'Valor bruto'], ['perc_iss', 'ISS (%)'], ['perc_irpj', 'IRPJ (%)'], ['valor_iss', 'Valor ISS'], ['valor_irpj', 'Valor IRPJ'], ['valor_liquido', 'Valor líquido']].map(([name, label]) => <Col xs={24} sm={8} key={name}><Form.Item name={name} label={label} rules={required}><InputNumber<string> stringMode min="0" max={name.startsWith('perc_') ? '100' : '99999999.99'} precision={2} decimalSeparator="," style={{ width: '100%' }} /></Form.Item></Col>)}</Row>
    <Button aria-label="Calcular impostos" loading={calculating} onClick={calculate}>Calcular pelos percentuais</Button>
    <Typography.Title level={5}>Renovações</Typography.Title>
    <Form.List name="renovacoes">{(fields, { add, remove }) => <>
      {fields.map(field => <section className="contract-line" key={field.key}><Form.Item name={[field.name, 'id']} hidden><Input /></Form.Item><Row gutter={12}><Col xs={24} sm={11}><DateInput name={[field.name, 'dt_data_inicio']} label={`Início da renovação ${field.name + 1}`} /></Col><Col xs={19} sm={11}><DateInput name={[field.name, 'dt_data_final']} label={`Fim da renovação ${field.name + 1}`} /></Col><Col xs={5} sm={2}><Button type="text" danger aria-label={`Remover renovação ${field.name + 1}`} icon={<DeleteOutlined />} onClick={() => remove(field.name)} style={{ marginTop: 29 }} /></Col></Row></section>)}
      <Button icon={<PlusOutlined />} aria-label="Adicionar renovação" onClick={() => add({})} disabled={fields.length >= 200}>Adicionar renovação</Button>
    </>}</Form.List>
  </>;
}
