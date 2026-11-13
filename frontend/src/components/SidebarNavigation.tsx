import { useEffect, useState } from 'react';
import { Menu } from 'antd';
import type { MenuProps } from 'antd';
import { ApartmentOutlined, AppstoreOutlined, AuditOutlined, BankOutlined, FileTextOutlined, SettingOutlined, ShoppingCartOutlined, SolutionOutlined, TeamOutlined } from '@ant-design/icons';
import { Link, useLocation } from 'react-router-dom';
import { activeNavigation, type NavigationEntry } from '../navigation';

const icons: Record<string, React.ReactNode> = {
  dashboard: <AppstoreOutlined/>, cadastro: <TeamOutlined/>, movimento: <SolutionOutlined/>, compras: <ShoppingCartOutlined/>,
  'contas-bancos': <BankOutlined/>, financeiro: <ApartmentOutlined/>, contabil: <AuditOutlined/>, relatorios: <FileTextOutlined/>,
  configuracoes: <SettingOutlined/>, recadastramento: <TeamOutlined/>, usuarios: <TeamOutlined/>,
};
function menuItems(entries: NavigationEntry[], selected: string): MenuProps['items'] {
  return entries.map(entry => ({ key: entry.key, icon: icons[entry.key] ? <span aria-hidden="true">{icons[entry.key]}</span> : undefined,
    label: entry.to ? <Link to={entry.to} aria-label={entry.accessibleLabel} aria-current={entry.key === selected ? 'page' : undefined}>{entry.label}</Link> : entry.label,
    ...(entry.children ? { children: menuItems(entry.children, selected) } : {}),
  }));
}
export function SidebarNavigation({ entries, onNavigate }: { entries: NavigationEntry[]; onNavigate: () => void }) {
  const location = useLocation(), active = activeNavigation(entries, location.pathname, location.search);
  const [openKeys, setOpenKeys] = useState(active.parents);
  const ancestors = active.parents.join('|');
  const groups: string[] = [];
  function collect(nodes: NavigationEntry[]) { for (const node of nodes) if (node.children) { groups.push(node.key); collect(node.children); } }
  collect(entries);
  const available = groups.join('|');
  useEffect(() => {
    const permitted = new Set(available.split('|'));
    setOpenKeys(previous => [...new Set([...previous.filter(key => permitted.has(key)), ...ancestors.split('|').filter(Boolean)])]);
  }, [location.pathname, location.search, ancestors, available]);
  return <nav className="sidebar-navigation" aria-label="Menu principal"><Menu theme="dark" mode="inline" inlineIndent={16}
    selectedKeys={active.key ? [active.key] : []} openKeys={openKeys} onOpenChange={setOpenKeys} items={menuItems(entries, active.key)} onClick={onNavigate}/></nav>;
}
