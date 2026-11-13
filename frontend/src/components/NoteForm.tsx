import { Col, DatePicker, Form, Input, InputNumber, Row, Switch } from 'antd';
import type { FormInstance } from 'antd';
import dayjs from 'dayjs';
import { RemoteSelect } from './RemoteSelect';
import { noteEndpoint } from '../noteTypes';
const required = [{ required: true, message: 'Preencha este campo.' }];
export function NoteForm({ form }: { form: FormInstance }) {
  const uf = Form.useWatch('uf', form);
  return <>
    <Form.Item name="contrato" label="Contrato" rules={required}><RemoteSelect url={noteEndpoint + 'opcoes/'} labelField="descricao" /></Form.Item>
    <Row gutter={16}><Col span={12}><Form.Item name="competencia" label="Mês da competência" rules={required}><InputNumber min={1} max={12} precision={0} /></Form.Item></Col><Col span={12}><Form.Item name="exercicio" label="Exercício" rules={required}><InputNumber min={1} max={9999} precision={0} /></Form.Item></Col></Row>
    <Form.Item name="numero" label="Número para consulta (se existente)"><Input maxLength={15} /></Form.Item>
    <Row gutter={16}>{[['dt_data_emissao', 'Data de emissão'], ['dt_data_vencimento', 'Vencimento']].map(([name, label]) => <Col span={12} key={name}><Form.Item name={name} label={label} rules={name === 'dt_data_emissao' ? required : []} getValueProps={value => ({ value: value ? dayjs(value) : null })} normalize={value => value?.toISOString() ?? null}><DatePicker format="DD/MM/YYYY" style={{ width: '100%' }} /></Form.Item></Col>)}</Row>
    <Row gutter={16}>{[['valor_bruto', 'Valor bruto'], ['imposto', 'ISS'], ['aliq_imposto', 'Alíquota ISS (%)'], ['valor_liquido', 'Valor líquido']].map(([name, label]) => <Col xs={24} sm={12} key={name}><Form.Item name={name} label={label} rules={required}><InputNumber<string> stringMode min="0" max={name === 'aliq_imposto' ? '100' : '99999999.99'} precision={2} decimalSeparator="," style={{ width: '100%' }} /></Form.Item></Col>)}</Row>
    <Form.Item name="texto_nota" label="Discriminação dos serviços" rules={required}><Input.TextArea rows={5} /></Form.Item>
    <Row gutter={16}><Col span={8}><Form.Item name="uf" label="UF da prestação"><RemoteSelect url="/clientes/api/ufs/" labelField="sigla" onChange={() => form.setFieldValue('cidade', null)} /></Form.Item></Col><Col span={16}><Form.Item name="cidade" label="Município da prestação"><RemoteSelect url={'/clientes/api/municipios/?uf=' + (uf ?? '')} labelField="descricao" disabled={!uf} /></Form.Item></Col></Row>
    {[['coigo_servico', 'Código do serviço', 5], ['codigo_cnae', 'CNAE', 8], ['codigo_tributacao_municipio', 'Código de tributação municipal', 15], ['descr_tributacao_municipio', 'Descrição de tributação', 80]].map(([name, label, max]) => <Form.Item key={name} name={String(name)} label={label}><Input maxLength={Number(max)} /></Form.Item>)}
    <Form.Item name="decimo_terceiro" label="Inclui décimo terceiro" valuePropName="checked"><Switch /></Form.Item>
  </>;
}
