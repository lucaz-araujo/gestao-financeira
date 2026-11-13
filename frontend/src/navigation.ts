export interface NavigationEntry {
  key: string;
  label: string;
  to?: string;
  accessibleLabel?: string;
  children?: NavigationEntry[];
}
interface VisibleRoute { key: string; label: string }

/** Hierarquia recuperada do menu Django; destinos usam as telas atuais. */
export function buildNavigation(routes: readonly VisibleRoute[], can: (permission: string) => boolean, restrictedUf = false): NavigationEntry[] {
  const allowed = new Map(routes.map(route => [route.key, route]));
  const leaf = (key: string, label?: string): NavigationEntry[] => {
    const route = allowed.get(key);
    return route ? [{ key, label: label ?? route.label, to: '/' + key }] : [];
  };
  const group = (key: string, label: string, children: NavigationEntry[]): NavigationEntry[] => children.length ? [{ key, label, children }] : [];
  const shortcut = (key: string, label: string, to: string, permitted: boolean, accessibleLabel = label): NavigationEntry[] => permitted ? [{ key, label, to, accessibleLabel }] : [];
  const cadastralReports = [
    ...shortcut('report-clientes', 'Clientes', '/relatorios?tipo=CL', can('clientes.view_cliente'), 'Relatório de clientes'),
    ...shortcut('report-parceiros', 'Parceiros', '/relatorios?tipo=PAR', can('clientes.view_parceiro'), 'Relatório de parceiros'),
    ...shortcut('report-nascimentos', 'Clientes / Data de nascimento', '/relatorios?tipo=NASC', can('clientes.view_cliente'), 'Relatório de aniversariantes'),
  ];
  const financialReports = [
    ...shortcut('report-inadimplentes', 'Inadimplentes', '/receitas?situacao=vencido', allowed.has('receitas')),
    ...shortcut('report-receber', 'Contas a receber', '/receitas?relatorio=receitas', allowed.has('receitas'), 'Relatório de contas a receber'),
    ...shortcut('report-pagar', 'Contas a pagar', '/despesas?relatorio=despesas', allowed.has('despesas'), 'Relatório de contas a pagar'),
    ...shortcut('report-transferencias', 'Transferências', '/transferencias?relatorio=transferencias', allowed.has('transferencias'), 'Relatório de transferências'),
    ...shortcut('report-cheques', 'Cheques emitidos', '/movimentos?relatorio=cheques', allowed.has('movimentos')),
    ...shortcut('report-analise', 'Análise financeira', '/fechamentos?analise=1', !restrictedUf && ['financeiro.view_docreceita', 'financeiro.view_docdespesa', 'financeiro.view_fechamentocaixa'].every(can)),
  ];
  const bankingReports = shortcut('report-movimentos', 'Lançamentos bancários', '/movimentos?relatorio=movimentos', allowed.has('movimentos'), 'Relatório de lançamentos bancários');
  const contractReports = [
    ...shortcut('report-contratos', 'Contratos', '/relatorios?tipo=CON_S', can('contratos.view_contrato'), 'Relatório de contratos'),
    ...shortcut('report-notas', 'Notas', '/relatorios?tipo=NF_ALL', can('notas.view_nota'), 'Relatório de notas'),
    ...shortcut('report-notas-pagas', 'Notas pagas', '/relatorios?tipo=NF_PAID', can('notas.view_nota'), 'Relatório de notas pagas'),
  ];
  const reports = [
    ...group('report-cadastrais', 'Cadastrais', cadastralReports),
    ...group('report-financeiros', 'Financeiros', financialReports),
    ...group('report-bancarios', 'Bancários', bankingReports),
    ...group('report-contratos-notas', 'Contratos / Notas', contractReports),
    ...shortcut('report-todos', 'Todos os relatórios cadastrais e fiscais', '/relatorios', cadastralReports.length > 0 || contractReports.length > 0),
  ];
  return [
    ...leaf('dashboard'),
    ...group('cadastro', 'Cadastro', [
      ...leaf('parceiros'), ...leaf('clientes'), ...leaf('bloqueios', 'Bloqueio de clientes'), ...leaf('produtos'), ...leaf('agenda', 'Contatos'),
    ]),
    ...group('movimento', 'Movimento', [...leaf('contratos'), ...leaf('notas')]),
    ...group('compras', 'Compras', [...leaf('compras-unidades'), ...leaf('compras-itens'), ...leaf('compras-fornecedores'), ...leaf('compras-solicitacoes'), ...leaf('compras-orcamentos')]),
    ...group('contas-bancos', 'Contas Bancos', [...leaf('bancos'), ...leaf('contas'), ...leaf('transferencias'), ...leaf('movimentos')]),
    ...group('financeiro', 'Financeiro', [
      ...leaf('servicos'), ...leaf('receitas'), ...leaf('despesas'),
      ...shortcut('conciliacao', 'Conciliação bancária', '/receitas?conciliar=1', allowed.has('receitas') && can('financeiro.add_recreceita')),
      ...leaf('fechamentos'), ...leaf('liberacoes'), ...leaf('chaves'),
    ]),
    ...group('contabil', 'Contábil', [...leaf('contabil-centros'), ...leaf('contabil-tipos'), ...leaf('contabil-planos'), ...leaf('contabil-lancamentos')]),
    ...group('relatorios', 'Relatórios', reports),
    ...group('configuracoes', 'Configurações', [...leaf('empresas'), ...leaf('ambiente-fiscal')]),
    ...leaf('recadastramento'),
    ...leaf('usuarios'),
  ];
}

export function activeNavigation(entries: NavigationEntry[], pathname: string, search: string) {
  const current = new URLSearchParams(search);
  let match = { key: '', parents: [] as string[], specificity: -1 };
  function visit(nodes: NavigationEntry[], parents: string[]) {
    for (const node of nodes) {
      if (node.children) visit(node.children, [...parents, node.key]);
      if (!node.to) continue;
      const [path, query = ''] = node.to.split('?');
      const expected = new URLSearchParams(query);
      if (path === pathname && [...expected].every(([key, value]) => current.get(key) === value) && expected.size > match.specificity) {
        match = { key: node.key, parents, specificity: expected.size };
      }
    }
  }
  visit(entries, []);
  return match;
}
