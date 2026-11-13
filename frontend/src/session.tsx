import { createContext, useContext, useEffect, useState, useRef } from 'react';
import type { ReactNode } from 'react';
import { api, ApiError, clearAccess, errorMessage, login, logout, refreshSession, setSessionExpiredHandler } from './api';
import type { Session } from './types';
interface Context { clearSession: () => void; user: Session | null; empresa?: number; booting: boolean; issue: string; signIn: (username: string, password: string) => Promise<void>; signOut: () => Promise<void>; selectEmpresa: (id: number) => Promise<void>; refreshUser: (preferred?: number) => Promise<void>; can: (permission: string) => boolean }
const SessionContext = createContext<Context | null>(null);
export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Session | null>(null);
  const [empresa, setEmpresa] = useState<number>();
  const [booting, setBooting] = useState(true);
  const [issue, setIssue] = useState('');
  const authEpoch = useRef(0);
  async function accept(next: Session, preferred: number | undefined, epoch: number) {
    if (epoch !== authEpoch.current) return;
    const saved = preferred ?? Number(sessionStorage.getItem('clientes_empresa'));
    const selected = next.empresas.find(e => e.id === saved)?.id ?? next.empresas[0]?.id;
    if (selected) await api('/empresa/api/selecionar/', { method: 'POST', body: JSON.stringify({ empresa: selected }) });
    if (epoch !== authEpoch.current) return;
    setUser(next);
    setEmpresa(selected);
    if (selected) sessionStorage.setItem('clientes_empresa', String(selected)); else sessionStorage.removeItem('clientes_empresa');
    setIssue('');
  }
  useEffect(() => {
    let active = true; const epoch = authEpoch.current;
    setSessionExpiredHandler(() => { authEpoch.current++; setUser(null); setEmpresa(undefined); setIssue('Sua sessão expirou. Entre novamente.'); });
    refreshSession().then(() => api<Session>('/clientes/api/auth/me/')).then(next => { if (active) return accept(next, undefined, epoch); })
      .catch(error => { if (active && !(error instanceof ApiError && error.status === 401)) setIssue(errorMessage(error)); })
      .finally(() => { if (active) setBooting(false); });
    return () => { active = false; };
  }, []);
  async function signIn(username: string, password: string) { const epoch = ++authEpoch.current; await login(username, password); const next = await api<Session>('/clientes/api/auth/me/'); await accept(next, undefined, epoch); }
  function clearSession() { authEpoch.current++; clearAccess(); setUser(null); setEmpresa(undefined); sessionStorage.removeItem('clientes_empresa'); setIssue(''); }
  async function signOut() { authEpoch.current++; await logout(); clearSession(); }
  async function selectEmpresa(id: number) { const epoch = authEpoch.current; if (user?.empresas.some(e => e.id === id)) { await api('/empresa/api/selecionar/', { method: 'POST', body: JSON.stringify({ empresa: id }) }); if (epoch !== authEpoch.current) return; setEmpresa(id); sessionStorage.setItem('clientes_empresa', String(id)); } }
  async function refreshUser(preferred?: number) { const epoch = authEpoch.current; await accept(await api<Session>('/clientes/api/auth/me/'), preferred, epoch); }
  return <SessionContext.Provider value={{ clearSession, user, empresa, booting, issue, signIn, signOut, selectEmpresa, refreshUser, can: permission => !!user?.permissions.includes(permission) }}>{children}</SessionContext.Provider>;
}
export function useSession() { const context = useContext(SessionContext); if (!context) throw Error('Sessão indisponível'); return context; }
