import logo from '../../../static/img/logo_layout.png';
import { useSession } from '../session';
import '../../../static/css/layout-print.css';

function clearPrintSelection() {
  document.querySelectorAll('[data-layout-print-target], [data-layout-print-ancestor]').forEach(node => { node.removeAttribute('data-layout-print-target'); node.removeAttribute('data-layout-print-ancestor'); });
  document.body.classList.remove('layout-print-mode');
}
function prepareSheet(sheet: HTMLElement) {
  clearPrintSelection();
  sheet.setAttribute('data-layout-print-target', 'true');
  let parent = sheet.parentElement;
  while (parent && parent !== document.body) { parent.setAttribute('data-layout-print-ancestor', 'true'); parent = parent.parentElement; }
  const issued = new Date().toLocaleString('pt-BR');
  sheet.querySelectorAll<HTMLElement>('.print-issued').forEach(node => { node.textContent = issued; });
  document.body.classList.add('layout-print-mode');
}
export function printSheet(id: string) {
  const sheet = document.getElementById(id);
  if (!sheet) return;
  prepareSheet(sheet);
  window.print();
}
if (typeof window !== 'undefined') {
  window.addEventListener('beforeprint', () => {
    if (document.querySelector('[data-layout-print-target]')) return;
    const sheets = [...document.querySelectorAll<HTMLElement>('.print-sheet')].filter(node => node.getBoundingClientRect().height > 0 && getComputedStyle(node).visibility !== 'hidden');
    const sheet = sheets.filter(node => node.classList.contains('contract-printable')).at(-1) ?? sheets.at(-1);
    if (sheet) prepareSheet(sheet);
  });
  window.addEventListener('afterprint', clearPrintSelection);
}

export function PrintHeader({ title, reference = 'Documento de gestão', subtitle, printOnly = false }: { title: string; reference?: string; subtitle?: string; printOnly?: boolean }) {
  const { user, empresa } = useSession();
  const company = user?.empresas.find(value => value.id === empresa);
  return <header className={'print-header' + (printOnly ? ' layout-print-only' : '')}>
    <div className="print-header-top"><div className="print-brand"><img src={logo} alt="Layout Sistemas"/><div><strong>LAYOUT SISTEMAS</strong><span>GESTÃO FINANCEIRA</span></div></div><span className="print-reference">{reference}</span></div>
    <div className="print-company">{company?.razao ?? 'Gestão Financeira'}</div>
    <h1>{title}</h1>{subtitle && <p className="print-subtitle">{subtitle}</p>}
    <div className="print-metadata">{company?.cnpj && <span><b>CNPJ</b> {company.cnpj}</span>}<span><b>Gerado em</b> <time className="print-issued">{new Date().toLocaleString('pt-BR')}</time></span></div>
  </header>;
}
export function PrintFooter() {
  return <footer className="print-footer layout-print-only"><span>Layout Sistemas</span><span>Gestão Financeira · Documento gerado eletronicamente</span></footer>;
}
