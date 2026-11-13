import { Table } from '../components/DataTable';
import { useEffect, useState } from 'react';
import { Alert, App, Button, Card, Col, Empty, Form, InputNumber, Progress, Row, Select, Space, Spin, Statistic, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { api, errorMessage } from '../api';
import { useSession } from '../session';

interface Period { mes: number; ano: number }
interface Month { competencia: number; cadastradas: number; com_pagamento_registrado: number }
interface Summary extends Period {
  empresa: number; atualizado_em: string;
  clientes: { total: number; ativos: number } | null;
  notas: { total: number; com_pagamento_registrado: number; canceladas: number; mensal: Month[] } | null;
  receitas: { documentos: number; valor_total: string; recebido: string; saldo: string; vencido: string; vencem_em_10_dias: string } | null;
  parceiros: { results: { id: number; instituicao: string; clientes: number; percentual: string }[]; sem_parceiro_autorizado: number } | null;
  alertas: { count: number; page: number; page_size: number; inicio: string; fim: string; results: { id: number; numero: string | null; cliente_nome: string; dt_data_final: string }[] } | null;
}
const months = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
const money = (value: string) => Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const date = (value: string) => value.split('-').reverse().join('/');

export function Dashboard() {
  const { empresa } = useSession(), { message } = App.useApp(), [form] = Form.useForm();
  const [period, setPeriod] = useState<Period>(), [data, setData] = useState<Summary>();
  const [page, setPage] = useState(1), [reload, setReload] = useState(0), [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false), [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    api<Period>('/dashboard/api/competencia/').then(value => { if (active) { setPeriod(value); form.setFieldsValue(value); } })
      .catch(e => { if (active) { setError(errorMessage(e)); setLoading(false); } });
    return () => { active = false; };
  }, [form]);
  useEffect(() => {
    if (!period || !empresa) return;
    const controller = new AbortController(); let active = true;
    setLoading(true); setError(''); setData(undefined);
    const query = new URLSearchParams({ mes: String(period.mes), ano: String(period.ano), pagina_alertas: String(page) });
    api<Summary>('/dashboard/api/resumo/?' + query, { signal: controller.signal }, empresa)
      .then(value => { if (active) setData(value); }).catch(e => { if (active) setError(errorMessage(e)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [empresa, period, page, reload]);
  async function apply(values: Period) {
    setSaving(true); setError('');
    try { const value = await api<Period>('/dashboard/api/competencia/', { method: 'PATCH', body: JSON.stringify(values) }); setPage(1); setPeriod(value); void message.success('Competência atualizada.'); }
    catch (e) { setError(errorMessage(e)); } finally { setSaving(false); }
  }
  const maximum = Math.max(1, ...(data?.notas?.mensal.map(month => month.cadastradas) ?? []));
  return <>
    <div className="page-heading"><div><div className="eyebrow">GESTÃO / VISÃO GERAL</div><h1>Visão geral</h1><p>Acompanhe a empresa selecionada com os dados disponíveis para sua conta.</p></div><Button icon={<ReloadOutlined />} onClick={() => setReload(value => value + 1)} loading={loading} disabled={!period} aria-label="Atualizar painel">Atualizar</Button></div>
    <Card style={{ marginBottom: 24 }}><Form form={form} layout="inline" onFinish={apply} requiredMark={false}>
      <Form.Item name="mes" label="Mês" rules={[{ required: true }]}><Select aria-label="Mês do painel" style={{ width: 150 }} options={months.map((label, i) => ({ value: i + 1, label }))}/></Form.Item>
      <Form.Item name="ano" label="Exercício" rules={[{ required: true }]}><InputNumber aria-label="Exercício do painel" min={1900} max={9999} precision={0}/></Form.Item>
      <Form.Item><Button type="primary" htmlType="submit" loading={saving}>Aplicar competência</Button></Form.Item>
    </Form></Card>
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 24 }}/>} {loading && <Spin aria-label="Carregando indicadores"/>}
    {data && <Space orientation="vertical" size={24} style={{ width: '100%' }}>
      <Row gutter={[16, 16]}>
        {data.clientes && <><Col xs={24} sm={12} lg={6}><Card><Statistic title="Clientes cadastrados" value={data.clientes.total}/><Link to="/clientes">Consultar clientes</Link></Card></Col><Col xs={24} sm={12} lg={6}><Card><Statistic title="Clientes ativos" value={data.clientes.ativos}/></Card></Col></>}
        {data.notas && <><Col xs={24} sm={12} lg={6}><Card><Statistic title="Notas na competência" value={data.notas.total}/><Link to="/notas">Consultar notas</Link></Card></Col><Col xs={24} sm={12} lg={6}><Card><Statistic title="Notas canceladas na competência" value={data.notas.canceladas}/></Card></Col></>}
      </Row>
      {data.receitas && <Card title="Receitas com vencimento no mês"><p>Valores dos documentos do mês selecionado; recebimentos registrados até o momento e saldo pendente. Vencidos são avaliados na data de hoje.</p><Row gutter={[16, 24]}>{([
        ['Valor dos documentos', data.receitas.valor_total], ['Recebido destes documentos', data.receitas.recebido], ['Saldo a receber', data.receitas.saldo], ['Saldo vencido', data.receitas.vencido], ['Saldo que vence em até 10 dias', data.receitas.vencem_em_10_dias],
      ] as const).map(([label, value]) => <Col xs={24} sm={12} lg={8} key={label}><Statistic title={label} value={money(value)}/></Col>)}</Row><p>{data.receitas.documentos} documento(s) no período. <Link to="/receitas">Consultar contas a receber</Link></p></Card>}
      {data.notas && <Card title={`Notas por competência — ${data.ano}`}><Typography.Paragraph type="secondary">Notas cadastradas, incluindo rascunhos e canceladas. Pagamento registrado é o marcador da nota; os valores financeiros estão no quadro de receitas.</Typography.Paragraph><div className="dashboard-chart" role="img" aria-label={`Notas cadastradas e com pagamento registrado por competência de ${data.ano}`}>
        {data.notas.mensal.map(month => <div className="dashboard-chart-row" key={month.competencia}><span>{months[month.competencia - 1].slice(0, 3)}</span><div className="dashboard-chart-track"><div className="dashboard-chart-bar" style={{ width: `${month.cadastradas / maximum * 100}%` }}/></div><span>{month.cadastradas} / {month.com_pagamento_registrado}</span></div>)}
      </div><Typography.Paragraph type="secondary">Contagens: cadastradas / com pagamento registrado.</Typography.Paragraph></Card>}
      {data.parceiros && <Card title="Clientes por parceiro"><p>Até dez parceiros com mais clientes no escopo da sua conta. Percentual sobre todos os clientes visíveis.</p>{data.parceiros.results.length ? data.parceiros.results.map(partner => <div key={partner.id} style={{ marginBottom: 16 }}><Typography.Text>{partner.instituicao} — {partner.clientes} cliente(s)</Typography.Text><Progress percent={Number(partner.percentual)} strokeColor="#bd252a"/></div>) : <Empty description="Nenhum cliente vinculado a parceiro autorizado."/>}<p>{data.parceiros.sem_parceiro_autorizado} cliente(s) sem parceiro autorizado neste escopo.</p></Card>}
      {data.alertas && <Card title="Vencimentos de contratos"><p>Contratos ativos do exercício {data.ano}, com vencimento de {date(data.alertas.inicio)} a {date(data.alertas.fim)} (30 dias antes e depois de hoje).</p><Table rowKey="id" size="small" scroll={{ x: 480 }} dataSource={data.alertas.results} columns={[
        { title: 'Contrato', dataIndex: 'numero', render: value => value || 'Sem número' }, { title: 'Cliente', dataIndex: 'cliente_nome' }, { title: 'Vencimento', dataIndex: 'dt_data_final', render: date },
      ]} pagination={{ current: data.alertas.page, pageSize: data.alertas.page_size, total: data.alertas.count, showSizeChanger: false, onChange: setPage }}/><Link to="/contratos">Consultar contratos</Link></Card>}
      <Typography.Text type="secondary">Atualizado em {new Date(data.atualizado_em).toLocaleString('pt-BR')}. Cada indicador respeita suas permissões de consulta.</Typography.Text>
    </Space>}
  </>;
}
