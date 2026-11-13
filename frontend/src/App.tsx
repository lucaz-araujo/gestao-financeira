import { Users } from './pages/Users';
import { buildNavigation } from './navigation';
import { SidebarNavigation } from './components/SidebarNavigation';
import { Recadastramento, recadResources } from './pages/Recadastramento';
import { Dashboard } from './pages/Dashboard';
import { Profile } from './pages/Profile';
import { PasswordRecovery, SignOut } from './pages/PasswordRecovery';
import { FiscalEnvironment } from './pages/FiscalEnvironment';
import { Companies } from './pages/Companies';
import { ServiceKeys } from './pages/ServiceKeys';
import { Agenda } from './pages/Agenda';
import { Services } from './pages/Services';
import { Purchases, type PurchaseResource } from './pages/Purchases';
import { Accounting, type AccountingResource } from './pages/Accounting';
import { Alert, App as AntApp, Avatar, Button, ConfigProvider, Drawer, Dropdown, Layout, Select, Spin } from 'antd';
import ptBR from 'antd/locale/pt_BR';
import { ApartmentOutlined, LogoutOutlined, MenuOutlined, DownOutlined, UserOutlined } from '@ant-design/icons';
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import dayjs from 'dayjs';
import 'dayjs/locale/pt-br';
import { SessionProvider, useSession } from './session';
import { Login } from './pages/Login';
import { ResourcePage } from './pages/ResourcePage';
import { Reports } from './pages/Reports';
import { Financial, type FinancialResource } from './pages/Financial';
import { Banking, type BankResource } from './pages/Banking';
import { Notes } from './pages/Notes';
import { Contracts } from './pages/Contracts';
import { errorMessage } from './api';
import type { Resource } from './types';
import { Brand } from './components/Brand';
dayjs.locale('pt-br');
const navigation = [
  { key: 'dashboard', label: 'Visão geral', permission: 'dashboard.summary' },
  { key: 'recadastramento', label: 'Recadastramento', permission: 'recadclientes.access' },
  { key: 'ambiente-fiscal', label: 'Ambiente fiscal', permission: 'configambiente.view_ambiente' },
  { key: 'empresas', label: 'Empresas', permission: 'empresa.view_empresa' },
  { key: 'chaves', label: 'Chaves de serviços', permission: 'chaves.view_chaveservico' },
  { key: 'agenda', label: 'Agenda de contatos', permission: 'agenda.view_contato' },
  { key: 'servicos', label: 'Serviços por cliente', permission: 'servicos.view_servico' },
  { key: 'compras-fornecedores', label: 'Fornecedores', permission: 'compras.view_fornecedor' },
  { key: 'compras-unidades', label: 'Unidades de medida', permission: 'compras.view_unidade' },
  { key: 'compras-itens', label: 'Itens de compra', permission: 'compras.view_itens' },
  { key: 'compras-solicitacoes', label: 'Solicitações de compra', permission: 'compras.view_solicitacao' },
  { key: 'compras-orcamentos', label: 'Orçamentos de compra', permission: 'compras.view_orcamento' },

  { key: 'contabil-planos', label: 'Planos de contas', permission: 'contabil.view_planocontas' },
  { key: 'contabil-centros', label: 'Centros de custo', permission: 'contabil.view_centrocusto' },
  { key: 'contabil-tipos', label: 'Tipos de despesa', permission: 'contabil.view_tipodespesa' },
  { key: 'contabil-lancamentos', label: 'Lançamentos contábeis', permission: 'contabil.view_lancamentos' },

  { key: 'receitas', label: 'Contas a receber', permission: 'financeiro.view_docreceita' },
  { key: 'despesas', label: 'Contas a pagar', permission: 'financeiro.view_docdespesa' },
  { key: 'fechamentos', label: 'Fechamentos de caixa', permission: 'financeiro.view_fechamentocaixa' },
  { key: 'clientes', label: 'Clientes', permission: 'clientes.view_cliente' },
  { key: 'bancos', label: 'Bancos', permission: 'conta.view_banco' },
  { key: 'contas', label: 'Contas bancárias', permission: 'conta.view_conta' },
  { key: 'movimentos', label: 'Movimentações', permission: 'conta.view_movimento' },
  { key: 'transferencias', label: 'Transferências', permission: 'conta.view_transferencia' },
  { key: 'notas', label: 'Notas fiscais', permission: 'notas.view_nota' },
  { key: 'contratos', label: 'Contratos', permission: 'contratos.view_contrato' },
  { key: 'produtos', label: 'Produtos', permission: 'produtos.view_produto' },
  { key: 'parceiros', label: 'Parceiros', permission: 'clientes.view_parceiro' },
  { key: 'liberacoes', label: 'Liberações', permission: 'financeiro.add_recreceita' },
  { key: 'bloqueios', label: 'Bloqueios', permission: 'clientes.view_liberacaodatas' },
  { key: 'usuarios', label: 'Cadastro de usuário', permission: 'usuario.view_usuario' },
];
function Workspace() {
  const { user, empresa, booting, selectEmpresa, can, signOut } = useSession();
  const { message } = AntApp.useApp();
  const location = useLocation(), navigate = useNavigate();
  const [mobileMenu, setMobileMenu] = useState(false);
  if (booting) return <div className="boot"><Spin size="large" /><p>Preparando seu espaço…</p></div>;
  if (location.pathname === '/recuperar-senha') return <PasswordRecovery />;
  if (location.pathname === '/sair') return <SignOut />;
  if (!user) return <Login />;
  const dashboardAllowed = ['clientes.view_cliente', 'notas.view_nota', 'financeiro.view_docreceita', 'contratos.view_contrato'].some(can);
  const recadAllowed = recadResources.some(resource => can('recadclientes.view_' + resource.model));
  const visible = navigation.filter(item => (item.key === 'recadastramento' && recadAllowed) || (item.key === 'dashboard' && dashboardAllowed) || can(item.permission) || (item.key === 'usuarios' && can('usuario.add_usuario')) || (item.key === 'empresas' && can('empresa.add_empresa')) || (item.key === 'chaves' && can('chaves.view_chaves')));
  const reports = can('clientes.view_cliente') || can('clientes.view_parceiro') || can('contratos.view_contrato') || can('notas.view_nota');
  const items = buildNavigation(visible, can, !!user.uf);
  const selected = location.pathname.split('/')[1];
  const accountRoute = ['perfil', 'sair'].includes(selected) || (!selected && !visible.length && !reports);
  if (!user.empresas.length && can('empresa.add_empresa') && !accountRoute && selected !== 'empresas') return <Navigate replace to="/empresas" />;
  const sidebar = <><Link className="brand" to="/"><Brand /></Link><div className="nav-caption">GESTÃO</div><SidebarNavigation entries={items} onNavigate={() => setMobileMenu(false)} /><div className="sidebar-foot"><div className="connection-dot" />Seu negócio, em dia.</div></>;
  async function exit() { try { await signOut(); navigate('/'); } catch (error) { void message.error(errorMessage(error)); } }
  return <Layout className="workspace"><Layout.Sider className="desktop-sidebar" width={234} theme="dark">{sidebar}</Layout.Sider><Drawer className="mobile-sidebar" placement="left" open={mobileMenu} onClose={() => setMobileMenu(false)} size={260}>{sidebar}</Drawer><Layout><Layout.Header className="topbar"><div className="company-block"><Button className="mobile-menu-trigger" type="text" icon={<MenuOutlined />} aria-label="Abrir menu" onClick={() => setMobileMenu(true)} /><span className="company-icon"><ApartmentOutlined /></span><div><span className="top-label">EMPRESA ATIVA</span><Select aria-label="Empresa ativa" value={empresa} onChange={id => { void selectEmpresa(id).catch(e => message.error(errorMessage(e))); }} options={user.empresas.map(e => ({ value: e.id, label: e.razao }))} variant="borderless" style={{ minWidth: 180, maxWidth: 310 }} /></div></div><div className="user-block"><Dropdown trigger={['click']} menu={{ items: [{ key: 'perfil', icon: <UserOutlined/>, label: <Link to="/perfil">Meu perfil</Link> }, { key: 'senha', label: <Link to="/perfil?senha=1">Alterar senha</Link> }] }}><button type="button" className="account-menu-trigger" aria-label="Menu do usuário"><Avatar src={user.avatar || undefined} alt="Foto do usuário" style={{ background: '#f2f2f2', color: '#222222' }}>{user.nome.slice(0, 2).toUpperCase()}</Avatar><span className="account-name">{user.nome}</span><DownOutlined aria-hidden="true"/></button></Dropdown><Button aria-label="Sair" type="text" icon={<LogoutOutlined />} onClick={exit}>Sair</Button></div></Layout.Header><Layout.Content className="main-content">
    {!user.empresas.length && !can('empresa.add_empresa') && !accountRoute ? <Alert type="warning" title="Nenhuma empresa vinculada à sua conta." description="Solicite ao administrador o vínculo com uma empresa para continuar." showIcon /> : !visible.length && !reports && !accountRoute ? <Alert type="warning" title="Sua conta ainda não tem permissões para este módulo." showIcon /> : <div key={empresa}>
      <Routes><Route path="perfil" element={<Profile />} /><Route path="sair" element={<SignOut />} />{visible.map(item => <Route key={item.key} path={item.key} element={item.key === 'usuarios' ? <Users /> : item.key === 'recadastramento' ? <Recadastramento /> : item.key === 'dashboard' ? <Dashboard /> : item.key === 'ambiente-fiscal' ? <FiscalEnvironment /> : item.key === 'empresas' ? <Companies /> : item.key === 'chaves' ? <ServiceKeys /> : item.key === 'agenda' ? <Agenda /> : item.key === 'servicos' ? <Services /> : item.key.startsWith('compras-') ? <Purchases key={item.key} resource={item.key.replace('compras-', '') as PurchaseResource} /> : item.key.startsWith('contabil-') ? <Accounting key={item.key} resource={item.key.replace('contabil-', '') as AccountingResource} /> : ['receitas', 'despesas', 'fechamentos'].includes(item.key) ? <Financial key={item.key + location.search} resource={item.key as FinancialResource} /> : item.key === 'contratos' ? <Contracts /> : item.key === 'notas' ? <Notes /> : ['bancos', 'contas', 'movimentos', 'transferencias'].includes(item.key) ? <Banking key={item.key} resource={item.key as BankResource} /> : <ResourcePage key={item.key} resource={item.key as Resource} />} />)}{reports && <Route path="relatorios" element={<Reports key={location.search} />} />}<Route path="*" element={<Navigate replace to={'/' + (visible[0]?.key ?? (reports ? 'relatorios' : 'perfil'))} />} /></Routes>
    </div>}
    <footer className="workspace-footer"><small>© 2014–{new Date().getFullYear()} <a href="https://www.layoutsistemas.com.br/" target="_blank" rel="noopener noreferrer"><strong>Layout Sistemas</strong></a>. Todos os direitos reservados.</small></footer>
  </Layout.Content></Layout></Layout>;
}
export default function App() { return <ConfigProvider locale={ptBR} theme={{ token: { colorPrimary: '#bd252a', colorInfo: '#bd252a', colorSuccess: '#252525', colorWarning: '#a52125', colorError: '#c5252a', borderRadius: 8, fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, sans-serif', colorText: '#222222', colorBgLayout: '#f5f5f5' }, components: { Button: { primaryShadow: 'none' }, Menu: { darkSubMenuItemBg: '#101010', darkPopupBg: '#171717', darkItemBg: '#171717', darkItemSelectedBg: '#a51f24', darkItemColor: '#d0d0d0' }, Table: { headerBg: '#fafafa', headerColor: '#737373', cellPaddingBlock: 19 } } }}><AntApp><BrowserRouter basename="/clientes/app"><SessionProvider><Workspace /></SessionProvider></BrowserRouter></AntApp></ConfigProvider>; }
