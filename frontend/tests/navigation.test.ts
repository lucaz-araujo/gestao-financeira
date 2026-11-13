import { describe, expect, it } from 'vitest';
import { activeNavigation, buildNavigation, type NavigationEntry } from '../src/navigation';
const routes = ['dashboard', 'parceiros', 'clientes', 'bloqueios', 'produtos', 'agenda', 'contratos', 'notas', 'receitas', 'despesas', 'fechamentos', 'contas', 'bancos', 'transferencias', 'movimentos', 'empresas', 'ambiente-fiscal'].map(key => ({ key, label: key }));
const all = () => true;
const leaves = (entries: NavigationEntry[]): NavigationEntry[] => entries.flatMap(entry => entry.children ? leaves(entry.children) : [entry]);

describe('navegação baseada no legado', () => {
  it('mantém a ordem de Cadastro e leva Contatos à agenda, sem confundir com contratos', () => {
    const cadastro = buildNavigation(routes, all).find(entry => entry.key === 'cadastro')!;
    expect(cadastro.label).toBe('Cadastro');
    expect(cadastro.children!.map(entry => entry.key)).toEqual(['parceiros', 'clientes', 'bloqueios', 'produtos', 'agenda']);
    expect(cadastro.children!.at(-1)).toMatchObject({ label: 'Contatos', to: '/agenda' });
    expect(cadastro.children![2].label).toBe('Bloqueio de clientes');
  });
  it('permite acesso somente a contatos sem exigir permissões de clientes para o grupo', () => {
    const tree = buildNavigation([{ key: 'agenda', label: 'Contatos' }], permission => permission === 'agenda.view_contato');
    expect(tree.map(entry => entry.key)).toEqual(['cadastro']);
    expect(tree[0].children!.map(entry => entry.key)).toEqual(['agenda']);
    expect(leaves(tree).some(entry => entry.to === '/clientes')).toBe(false);
  });
  it('omite grupos vazios e mantém o perfil fora da barra lateral', () => {
    expect(buildNavigation([], () => false)).toEqual([]);
    expect(leaves(buildNavigation(routes, all)).some(entry => entry.key === 'perfil')).toBe(false);
  });
  it('mostra Cadastro de usuário somente quando a rota é autorizada', () => {
    expect(leaves(buildNavigation([{ key: 'usuarios', label: 'Cadastro de usuário' }], () => false))).toEqual([{ key: 'usuarios', label: 'Cadastro de usuário', to: '/usuarios' }]);
    expect(leaves(buildNavigation([], () => false))).toEqual([]);
  });
  it('separa relatórios cadastrais, financeiros, bancários e de contratos/notas', () => {
    const reports = buildNavigation(routes, all).find(entry => entry.key === 'relatorios')!;
    expect(reports.children!.filter(entry => entry.children).map(entry => entry.label)).toEqual(['Cadastrais', 'Financeiros', 'Bancários', 'Contratos / Notas']);
    expect(leaves(reports.children!).find(entry => entry.key === 'report-parceiros')).toMatchObject({ to: '/relatorios?tipo=PAR', accessibleLabel: 'Relatório de parceiros' });
  });
  it('seleciona o relatório exato pelo tipo e abre seus ancestrais no acesso direto', () => {
    const tree = buildNavigation(routes, all);
    expect(activeNavigation(tree, '/relatorios', '?page=2&tipo=PAR')).toMatchObject({ key: 'report-parceiros', parents: ['relatorios', 'report-cadastrais'] });
    expect(activeNavigation(tree, '/clientes', '')).toMatchObject({ key: 'clientes', parents: ['cadastro'] });
    expect(activeNavigation(tree, '/receitas', '?relatorio=receitas')).toMatchObject({ key: 'report-receber', parents: ['relatorios', 'report-financeiros'] });
    expect(activeNavigation(tree, '/receitas', '?situacao=vencido')).toMatchObject({ key: 'report-inadimplentes', parents: ['relatorios', 'report-financeiros'] });
  });
  it('exige as permissões da conciliação e da análise consolidada', () => {
    const basic = leaves(buildNavigation(routes, () => false));
    expect(basic.some(entry => entry.key === 'conciliacao' || entry.key === 'report-analise')).toBe(false);
    const restricted = leaves(buildNavigation(routes, all, true));
    expect(restricted.some(entry => entry.key === 'report-analise')).toBe(false);
    expect(restricted.some(entry => entry.key === 'conciliacao')).toBe(true);
  });
});
