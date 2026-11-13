import { Alert, Button, Form, Input, Typography } from 'antd';
import { Link } from 'react-router-dom';
import { useState } from 'react';
import { errorMessage } from '../api';
import { useSession } from '../session';
import { Brand } from '../components/Brand';
export function Login() {
  const { signIn, issue } = useSession();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  async function submit(values: { username: string; password: string }) {
    setLoading(true); setError('');
    try { await signIn(values.username, values.password); const next = new URLSearchParams(window.location.search).get('next'); if (next && next.startsWith('/') && !next.startsWith('//') && !next.includes('\\') && new URL(next, window.location.origin).origin === window.location.origin) window.location.assign(next); } catch (e) { setError(errorMessage(e)); } finally { setLoading(false); }
  }
  return <div className="login-shell"><section className="login-story"><div className="brand"><Brand /></div><div><div className="eyebrow">RELACIONAMENTOS QUE MOVEM O NEGÓCIO</div><h1>Uma visão clara.<br />Cada cliente<br /><em>mais perto.</em></h1><p>Cadastros, parceiros e liberações conectados à sua operação financeira.</p></div><small>Seu espaço de trabalho, organizado.</small></section><main className="login-card"><div className="eyebrow">BEM-VINDO DE VOLTA</div><Typography.Title level={2}>Entre no seu espaço</Typography.Title><Typography.Paragraph type="secondary">Use suas credenciais do Gestão Financeira.</Typography.Paragraph>{(error || issue) && <Alert role="alert" type="error" title={error || issue} showIcon style={{ marginBottom: 24 }} />}<Form layout="vertical" onFinish={submit} requiredMark={false}><Form.Item name="username" label="Usuário" rules={[{ required: true, message: 'Informe seu usuário.' }]}><Input autoComplete="username" size="large" /></Form.Item><Form.Item name="password" label="Senha" rules={[{ required: true, message: 'Informe sua senha.' }]}><Input.Password autoComplete="current-password" size="large" /></Form.Item><Button block type="primary" size="large" htmlType="submit" loading={loading}>Entrar</Button></Form><p><Link to="/recuperar-senha">Esqueci minha senha</Link></p><p className="login-note">O acesso aos dados respeita as empresas e permissões da sua conta.</p></main></div>;
}
