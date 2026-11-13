import { Col, Form, Input, InputNumber, Row, Select } from 'antd';

const required = [{ required: true, message: 'Preencha este campo.' }];

export function ProdutoForm() {
  return <>
    <Form.Item name="descricao" label="Descrição" rules={[...required, { whitespace: true, message: 'Informe a descrição.' }]}>
      <Input maxLength={60} autoFocus />
    </Form.Item>
    <Row gutter={16}>
      <Col xs={24} sm={12}>
        <Form.Item name="sigla" label="Sigla" rules={[...required, { whitespace: true, message: 'Informe a sigla.' }]}>
          <Input maxLength={5} />
        </Form.Item>
      </Col>
      <Col xs={24} sm={12}>
        <Form.Item name="tipo_produto" label="Tipo" rules={required}>
          <Select options={[{ value: 'P', label: 'Produto' }, { value: 'S', label: 'Serviço' }]} />
        </Form.Item>
      </Col>
    </Row>
    <Form.Item name="valor" label="Valor" rules={required} extra="Informe o preço em reais, com até duas casas decimais.">
      <InputNumber<string> stringMode min="0" max="99999999.99" precision={2} decimalSeparator="," prefix="R$" style={{ width: '100%' }} />
    </Form.Item>
  </>;
}
